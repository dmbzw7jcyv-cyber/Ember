// bridge.js — Ember Backend Server
const express = require('express');
const cors = require('cors');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const net = require('net');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(express.json());
app.use(express.static('.'));

// ============================================================
// STATE
// ============================================================
const state = {
    attached: false,
    pipeConnected: false,
    injectorProcess: null,
    pipeClient: null,
    robloxPid: null
};

// ============================================================
// HELPERS
// ============================================================
function log(msg, type = 'info') {
    const prefix = type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️';
    console.log(`[bridge] ${prefix} ${msg}`);
}

function findRobloxPid() {
    return new Promise((resolve) => {
        if (process.platform !== 'win32') {
            resolve(null);
            return;
        }
        exec('tasklist /FI "IMAGENAME eq RobloxPlayerBeta.exe" /NH', (err, stdout) => {
            if (err) { resolve(null); return; }
            const lines = stdout.split('\n').filter(l => l.includes('RobloxPlayerBeta.exe'));
            if (lines.length === 0) { resolve(null); return; }
            const parts = lines[0].trim().split(/\s+/);
            const pid = parseInt(parts[1]);
            resolve(isNaN(pid) ? null : pid);
        });
    });
}

// ============================================================
// NAMED PIPE CLIENT
// ============================================================
function connectPipe() {
    if (state.pipeClient) return;

    log('Connecting to named pipe...', 'info');
    state.pipeClient = net.createConnection('\\\\.\\pipe\\EmberPipe', () => {
        state.pipeConnected = true;
        log('Payload connected via pipe.', 'success');
    });

    state.pipeClient.on('data', (data) => {
        const msg = data.toString().trim();
        log(`[payload] ${msg}`, 'info');
    });

    state.pipeClient.on('end', () => {
        log('Pipe disconnected.', 'error');
        state.pipeConnected = false;
        state.pipeClient = null;
    });

    state.pipeClient.on('error', (err) => {
        log(`Pipe error: ${err.message}`, 'error');
        state.pipeConnected = false;
        state.pipeClient = null;
    });
}

function sendToPipe(script) {
    if (!state.pipeClient || !state.pipeConnected) {
        log('Pipe not connected.', 'error');
        return false;
    }
    state.pipeClient.write(script + '\n');
    return true;
}

// ============================================================
// ROUTES
// ============================================================

app.get('/api/status', (req, res) => {
    res.json({
        attached: state.attached,
        pipeConnected: state.pipeConnected,
        injectorRunning: state.injectorProcess !== null && !state.injectorProcess.killed,
        robloxPid: state.robloxPid
    });
});

app.post('/api/attach', async (req, res) => {
    if (state.attached) {
        return res.json({ success: true, message: 'Already attached.' });
    }

    const pid = await findRobloxPid();
    if (!pid) {
        return res.status(400).json({ success: false, error: 'Roblox is not running.' });
    }
    state.robloxPid = pid;
    log(`Found Roblox at PID: ${pid}`, 'success');

    const injectorPath = path.join(__dirname, '..', '..', 'build', 'ember_injector.exe');
    const dllPath = path.join(__dirname, '..', '..', 'build', 'payload.dll');

    if (!fs.existsSync(injectorPath)) {
        return res.status(500).json({ success: false, error: 'Injector not found.' });
    }
    if (!fs.existsSync(dllPath)) {
        return res.status(500).json({ success: false, error: 'Payload DLL not found.' });
    }

    log('Spawning injector...', 'info');
    state.injectorProcess = spawn(injectorPath, [dllPath, pid.toString()]);

    state.injectorProcess.stdout.on('data', (data) => {
        const msg = data.toString().trim();
        log(`[injector] ${msg}`, 'info');
        if (msg.includes('Injection successful')) {
            state.attached = true;
            log('Attached to Roblox.', 'success');
            setTimeout(connectPipe, 500);
        }
    });

    state.injectorProcess.stderr.on('data', (data) => {
        log(`[injector error] ${data.toString().trim()}`, 'error');
    });

    state.injectorProcess.on('close', (code) => {
        log(`Injector exited with code ${code}`, 'info');
        state.attached = false;
        state.pipeConnected = false;
        state.injectorProcess = null;
    });

    res.json({ success: true, message: 'Injector started.' });
});

app.post('/api/execute', (req, res) => {
    const { script } = req.body;
    if (!script) {
        return res.status(400).json({ success: false, error: 'No script provided.' });
    }

    if (!state.attached || !state.pipeConnected) {
        return res.status(400).json({ success: false, error: 'Not attached to Roblox or pipe not ready.' });
    }

    const sent = sendToPipe(script);
    if (sent) {
        res.json({ success: true, message: 'Script sent to payload.' });
    } else {
        res.status(500).json({ success: false, error: 'Failed to send script.' });
    }
});

app.post('/api/detach', (req, res) => {
    if (state.injectorProcess) {
        state.injectorProcess.kill();
        state.injectorProcess = null;
    }
    if (state.pipeClient) {
        state.pipeClient.destroy();
        state.pipeClient = null;
    }
    state.attached = false;
    state.pipeConnected = false;
    state.robloxPid = null;
    log('Detached.', 'info');
    res.json({ success: true, message: 'Detached.' });
});

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'ui', 'index.html'));
});

app.listen(PORT, () => {
    log(`Ember Bridge running on http://localhost:${PORT}`, 'success');
    log(`Open http://localhost:${PORT} in your browser.`, 'info');
});