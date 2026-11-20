SPANDY SHOWS — See your code, step by step.
Portable edition for Windows 10/11, Intel/AMD 64-bit computers.

1. Copy the ZIP to the other computer.
2. Right-click the ZIP and choose Extract All. Finish extracting the whole folder.
3. Open the extracted folder and double-click Start Spandy Shows.exe.
4. Spandy Shows opens in your default web browser when the local server is ready.

No Python, Java, C, Node.js, package manager or administrator installation is
required. All runtimes and the built website are included. Initial startup can
take a few seconds. Keep the extracted folder together; do not move just the EXE.
Do not open the launcher from inside the ZIP preview.

Use Stop Spandy Shows.exe when finished. Closing the browser leaves the local
server running. Opening Start again reuses this copy's server. If port 8000 is
already used, the launcher selects another free local port automatically.

Extract into a writable folder such as Desktop or Documents. Stop the app before
moving, renaming or deleting the folder. No startup task or system PATH change
is created. Saved browser programs stay in that browser; server saves belong to
this extracted copy. A different local port has separate browser storage.

This edition is for running your own trusted code on your computer. It listens
only on 127.0.0.1. It is not an internet-hosted website or an untrusted-code
sandbox. Phones, tablets, macOS, Linux and Windows ARM are not this package's
target platforms. The existing language/input/time/trace limits still apply.

If startup fails, see .portable/launcher.log, .portable/bootstrap.log and
.portable/server.log in the extracted folder. Windows may flag a newly built,
unsigned EXE. This package is not signed or a Microsoft-verified installer;
follow the device's normal software policy rather than disabling protection.

All included components and their license notices are retained. See
THIRD-PARTY-NOTICES.txt and the license/legal files inside runtime/.
The editable website source is included in app/. The launcher source is in
app/portable/. Verification results are in PORTABLE-VERIFICATION.txt.
