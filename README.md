# GTK and Python for Windows

This project builds the Python and GTK framework for BleachBit
to use on Microsoft Windows. This includes introspection support
and a PyGObject wheel. We use Microsoft Visual C++ and vcpkg instead
of gcc and msys2.

As of 2025-06-10, this project builds
* Python 3.11.11
* GTK 3.24.43
* PyGObject 3.52.3

The build environment is GitHub Actions with MSVC++ 2022.
For more information about the build environment and build
process, see the [GitHub Action YAML files](https://github.com/bleachbit/pygtkwin/tree/main/.github/workflows)
or [logs](https://github.com/bleachbit/pygtkwin/actions).

Perhaps you are looking for a PyGTK all in one (AIO) installer,
but the others you found were years out of date? If you need to
run GTK on Windows, try this repository plus the
[install script](https://github.com/bleachbit/bleachbit/blob/master/windows/python-gtk3-install.ps1)
from the BleachBit repository.

Copyright (C) 2025 by Andrew Ziem. All rights reserved.
See [LICENSE](LICENSE) for license information.

Special thanks to @soylent-io for work to keep BleachBit
running on Windows.
