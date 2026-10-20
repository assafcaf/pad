// Preloaded into every vitest worker by runners/vitest.sh (NODE_OPTIONS=--import <this file>).
//
// contract-fast: with PAD_TIER=fast, a test that opens or listens on a socket, or starts a
// subprocess, fails at the call.
// leak-check: every process a test starts is appended as `<pid> <command>` to
// $PAD_REPORT_DIR/spawned; the adapter reports the ones still alive when the run ends as
// `LEAK <pid> <command>`.
//
// Only a vitest worker is touched (vitest's own main process starts the workers).
import net from "node:net";
import cp from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { syncBuiltinESMExports } from "node:module";

const inWorker = process.env.VITEST_POOL_ID !== undefined || process.env.VITEST_WORKER_ID !== undefined;
const fast = process.env.PAD_TIER === "fast";
const report = process.env.PAD_REPORT_DIR;

if (inWorker) {
  const refuse = (what) => {
    throw new Error(`PAD fast-tier contract: a fast test must not ${what}`);
  };

  if (fast) {
    const connect = net.Socket.prototype.connect;
    net.Socket.prototype.connect = function (...a) {
      refuse("open a socket");
      return connect.apply(this, a);
    };
    const listen = net.Server.prototype.listen;
    net.Server.prototype.listen = function (...a) {
      refuse("open a socket");
      return listen.apply(this, a);
    };
    for (const fn of ["spawnSync", "execSync", "execFileSync"]) {
      cp[fn] = () => refuse("start a subprocess");
    }
  }

  const note = (child, cmd, args) => {
    if (report && child && child.pid) {
      try {
        fs.mkdirSync(report, { recursive: true });
        const line = [cmd, ...(Array.isArray(args) ? args : [])].join(" ").replace(/\s+/g, " ").slice(0, 300);
        fs.appendFileSync(path.join(report, "spawned"), `${child.pid} ${line}\n`);
      } catch {}
    }
    return child;
  };

  for (const fn of ["spawn", "execFile", "fork", "exec"]) {
    const orig = cp[fn];
    cp[fn] = function (cmd, args, ...rest) {
      if (fast) refuse("start a subprocess");
      return note(orig.call(this, cmd, args, ...rest), cmd, args);
    };
  }
  // named imports (`import { spawn } from "node:child_process"`) see the patched functions
  syncBuiltinESMExports();
}
