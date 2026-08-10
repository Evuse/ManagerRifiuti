"""PyInstaller entry point kept outside the package for reliable relative imports."""

from manager_rifiuti.app import main

raise SystemExit(main())
