# Publish Spandy Shows for Windows

## Microsoft Store

1. Register as a Windows app developer using your own Microsoft account. Complete identity verification in Microsoft's portal. [Developer registration](https://storedeveloper.microsoft.com/)
2. In Partner Center, open **Apps and games**, create an **MSIX** app and reserve **Spandy Shows** if the name is available. Open the app's **Product identity** page. Copy `Package/Identity/Name`, `Package/Identity/Publisher` and `Package/Properties/PublisherDisplayName`. These public values identify the app. [Partner Center](https://partner.microsoft.com/dashboard/)
3. Build the desktop folder using the project's desktop build instructions. Package it with the three exact values and the reserved display name. The example assumes a Windows SDK installation, an x64 desktop folder and the current app name. Use a new version number for each release.

   ```powershell
   python scripts/build_store.py --bundle "../release/desktop/Spandy Shows" --makeappx "C:/path/to/x64/makeappx.exe" --name "<Package/Identity/Name>" --publisher "<Package/Identity/Publisher>" --publisher-display-name "<Package/Properties/PublisherDisplayName>" --version 1.2.0.0 --output "../release/Spandy-Shows-Store.msix"
   ```

4. Create a submission. Upload the MSIX and complete the listing, age rating, pricing, screenshots, support contact and privacy declarations. The short description can be “Write Python, Java and C programs and see how their values change, step by step.” Explain the requested full-trust capability in the submission: Spandy Shows starts local language runtimes and debuggers to run code the user enters, reads interactive input and saves named programs on the device. [Store readiness checklist](https://learn.microsoft.com/en-us/windows/apps/publish/store-readiness-checklist)
5. Test the Store-delivered build on a separate Windows 11 x64 PC with Smart App Control enabled. Use a private audience or package flight first where available. Test launch, save/reopen, and Run and Visualize with input in each language. In C, compile and run a new program to exercise creation and launch of its executable. Test upgrades with an existing saved program. Record any blocked component. Microsoft signs the package after certification. Share the public Store listing when the release is approved and tested. [Microsoft signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)

## Free signing for the GitHub installer

1. The owner published the MIT license for the original Spandy Shows code. Include it in future source and binary distributions. Review the bundled runtimes, fonts and other components under their own terms and retain upstream notices. The public repository provides the 1.2.0 source archive and download guide. [Project license](https://github.com/spandandey961-max/spandy-shows/blob/main/LICENSE) · [SignPath eligibility](https://signpath.org/terms)
2. Use the checked-in `spandy-shows/` source and build scripts for review. Build from a specific commit and keep the build record. Enable two-factor authentication for project members and identify who reviews changes and who approves releases.
3. Apply as the owner. Use the project name **Spandy Shows**, the repository `https://github.com/spandandey961-max/spandy-shows` and the release `https://github.com/spandandey961-max/spandy-shows/releases/tag/v1.2.0`. Describe it as an offline Windows desktop app for learning Python, Java and C. Explain that it bundles Electron, CPython, Eclipse Temurin and WinLibs GCC/GDB and that students' C programs generate local executables. Ask which project-built artifacts qualify for signing. Provide genuine project history, license details and maintainer information. [SignPath application](https://signpath.org/apply)
4. After approval, connect the verified build, set the signing policy and approvers, and build a new release. Preserve upstream signatures. Confirm eligibility of the customized Electron launcher with the provider. Sign and timestamp eligible artifacts in build order, finishing with the installer. Verify the final Windows signatures and generate checksums from the signed release.
5. Download the signed installer onto a second protected PC. Test the same installation and language workflows as the Store build. Only then publish the tested GitHub release and update the download link.

### Findings from the 1.2.0 signing check

| File examined | Windows signature status |
| --- | --- |
| Release installer | Unsigned |
| Desktop launcher in the staged build | Unsigned |
| Python interpreter, Java launcher and Java compiler in the staged build | Valid |
| C compiler and debugger in the staged build | Unsigned |

Across the staged desktop's 465 files with Windows executable or library extensions (.exe, .dll, .pyd, .node, .sys and .ocx), Windows reported 177 valid signatures and 288 unsigned files. Signature status alone does not predict which files will be blocked. Windows may also evaluate helper processes, libraries and generated programs during use. [Microsoft's Smart App Control test guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/test-your-app-with-smart-app-control)
