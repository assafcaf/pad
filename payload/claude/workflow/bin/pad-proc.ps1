# The Windows half of pad-proc.sh: run a command inside a job object, so that killing this host
# process (or ending it) kills every process the command started, detached or re-parented.
#
#   powershell -NoProfile -File pad-proc.ps1 job-run <bash.exe> <script.sh> <peak-file>
#
# Starts `<bash.exe> <script.sh>` with this host's stdio, inside a job object with
# KILL_ON_JOB_CLOSE. Writes the job's peak memory, in GB, to <peak-file> when the command ends and
# exits with the command's exit code. Exit 64 on usage.
param(
  [string]$Verb,
  [string]$Bash,
  [string]$Script,
  [string]$PeakFile
)

if ($Verb -ne 'job-run' -or -not $Bash -or -not $Script) {
  [Console]::Error.WriteLine('usage: pad-proc.ps1 job-run <bash.exe> <script.sh> <peak-file>')
  exit 64
}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class PadJob {
  [StructLayout(LayoutKind.Sequential)] public struct BASIC {
    public long PerProcessUserTimeLimit; public long PerJobUserTimeLimit; public uint LimitFlags;
    public UIntPtr MinimumWorkingSetSize; public UIntPtr MaximumWorkingSetSize;
    public uint ActiveProcessLimit; public UIntPtr Affinity; public uint PriorityClass;
    public uint SchedulingClass; }
  [StructLayout(LayoutKind.Sequential)] public struct IO {
    public ulong a; public ulong b; public ulong c; public ulong d; public ulong e; public ulong f; }
  [StructLayout(LayoutKind.Sequential)] public struct EXTENDED {
    public BASIC Basic; public IO Io; public UIntPtr ProcessMemoryLimit; public UIntPtr JobMemoryLimit;
    public UIntPtr PeakProcessMemoryUsed; public UIntPtr PeakJobMemoryUsed; }
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr CreateJobObject(IntPtr a, string n);
  [DllImport("kernel32.dll")] public static extern bool SetInformationJobObject(IntPtr j, int c, ref EXTENDED i, int l);
  [DllImport("kernel32.dll")] public static extern bool QueryInformationJobObject(IntPtr j, int c, ref EXTENDED i, int l, IntPtr r);
  [DllImport("kernel32.dll")] public static extern bool AssignProcessToJobObject(IntPtr j, IntPtr p);
  public static IntPtr Create() {
    IntPtr j = CreateJobObject(IntPtr.Zero, null);
    EXTENDED e = new EXTENDED();
    e.Basic.LimitFlags = 0x2000;
    SetInformationJobObject(j, 9, ref e, Marshal.SizeOf(typeof(EXTENDED)));
    return j;
  }
  public static double PeakGb(IntPtr j) {
    EXTENDED e = new EXTENDED();
    if (!QueryInformationJobObject(j, 9, ref e, Marshal.SizeOf(typeof(EXTENDED)), IntPtr.Zero)) return 0;
    return e.PeakJobMemoryUsed.ToUInt64() / 1073741824.0;
  }
}
'@ -ErrorAction Stop

$job = [PadJob]::Create()
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $Bash
$psi.Arguments = '"' + $Script + '"'
$psi.UseShellExecute = $false
$p = [System.Diagnostics.Process]::Start($psi)
[void][PadJob]::AssignProcessToJobObject($job, $p.Handle)
$p.WaitForExit()
$code = $p.ExitCode
if ($PeakFile) {
  [System.IO.File]::WriteAllText($PeakFile, ([PadJob]::PeakGb($job)).ToString('0.###', [Globalization.CultureInfo]::InvariantCulture) + "`n")
}
exit $code
