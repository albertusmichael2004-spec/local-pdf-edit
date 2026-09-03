# Repository structure

```text
pdf_workbench/
├── apps/
│   └── android/          Native Kotlin + Jetpack Compose application
├── backend/              Desktop FastAPI processing engine
├── frontend/             Desktop PyWebView user interface
├── data/                 Desktop runtime data and bundled assets
├── distribution/         Desktop packaging configuration
├── scripts/              Desktop development and maintenance scripts
├── tests/                Desktop Python test suite
├── desktop.py            Desktop process composition root
└── run.py                Desktop development launcher
```

The Android project is an independent Gradle build. It must not add generated
Gradle files, Android SDK paths, APKs, or Android dependencies to the desktop
runtime. The desktop files remain at the root until a dedicated migration can
move the Python package and launcher atomically without breaking imports.

Within `apps/android/app/src/main/java`, packages follow feature-first clean
boundaries:

- `app`: composition root and top-level navigation.
- `core`: reusable design tokens and models.
- `domain`: pure Kotlin contracts and use cases.
- `data`: Android framework adapters.
- `feature`: Compose screens and ViewModels.
