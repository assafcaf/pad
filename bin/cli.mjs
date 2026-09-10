#!/usr/bin/env node
// Thin launcher for install.sh.
//
// The installer is bash and stays bash: it is the one implementation, and a second one in
// JavaScript would drift from it the first time either changed. This file only finds a bash
// to run it with, forwards the arguments, and passes the exit code back.
//
//   npx github:assafcaf/dispatch-skills
//   npx github:assafcaf/dispatch-skills --tracker github --key ENG
//   npx github:assafcaf/dispatch-skills --dry-run

import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const script = join(root, "install.sh");

if (!existsSync(script)) {
  console.error(`dispatch-skills: install.sh not found at ${script}`);
  process.exit(1);
}

// On Windows, prefer Git Bash explicitly. A bare `bash` there often resolves to WSL's, which
// runs in a different filesystem namespace — it would install into the WSL home, not the one
// Claude Code reads.
function findBash() {
  if (process.platform !== "win32") return "bash";

  const candidates = [
    process.env.GIT_BASH,
    join(process.env.ProgramFiles ?? "C:\\Program Files", "Git", "bin", "bash.exe"),
    join(process.env["ProgramFiles(x86)"] ?? "C:\\Program Files (x86)", "Git", "bin", "bash.exe"),
    join(process.env.LOCALAPPDATA ?? "", "Programs", "Git", "bin", "bash.exe"),
  ].filter(Boolean);

  for (const c of candidates) if (existsSync(c)) return c;

  console.error("dispatch-skills: could not find Git Bash.");
  console.error("Install Git for Windows, or set GIT_BASH to your bash.exe.");
  console.error("Falling back to whatever `bash` is on PATH — if that is WSL, this will");
  console.error("install into the WSL home directory rather than the Windows one.");
  return "bash";
}

const result = spawnSync(findBash(), [script, ...process.argv.slice(2)], {
  stdio: "inherit",   // keeps the --wire prompt interactive
  cwd: process.cwd(), // so `--project` with no argument means the caller's directory
});

if (result.error) {
  console.error(`dispatch-skills: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
