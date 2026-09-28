# Internship report — build instructions

## Compiling

This document **must** be compiled with **XeLaTeX** (or LuaLaTeX), not
pdfLaTeX — the Arabic abstract requires native Unicode + right-to-left
script support via `polyglossia`/`fontspec`, which pdfLaTeX cannot do.

```bash
cd report
xelatex main.tex
xelatex main.tex   # run twice: resolves the table of contents / cross-references
```

The easiest way to avoid any local font/package gaps is to upload this
`report/` folder to [Overleaf](https://overleaf.com) (New Project → Upload
Project) and set the compiler to **XeLaTeX** in the project's menu — Overleaf
ships a full TeX Live install, including the `amiri` Arabic font this
document uses by default.

If `Amiri` is not available in your local TeX installation, edit this line
near the top of `main.tex` and point it at any Arabic-capable font you do
have installed (e.g. `Scheherazade New`, `Noto Naskh Arabic`, or `Tahoma` on
Windows):

```latex
\newfontfamily\arabicfont[Script=Arabic]{Amiri}
```

## Required assets you still need to add

Three institutional logo files are referenced but **not included** here —
they must be real, so add your own copies at these exact paths:

- `report/images/insat2.jpg` — INSAT logo
- `report/images/ucar.png` — University of Carthage logo
- `report/images/nadas_logo.png` — Nadas Group logo

Everything else the report references (5 screenshots under
`report/images/screens/`) is already in place — real screenshots taken from
the actual running application during development, not mockups.

## Page budget

The brief for this report caps it at 27 pages. This source was written to
land close to that target, but actual pagination depends on your local
font metrics and cannot be verified without compiling. After your first
successful compile, check the page count and, if it runs long, the first
things to trim are:
- the figure widths in Chapter IV (currently `0.8`–`0.95\textwidth`),
- Chapter II's "State of the Art" prose (Section II.1), and
- the Gantt table's row count in Chapter I.

## What's in this folder

```
report/
├── main.tex            The full report source
├── README.md            This file
└── images/
    ├── insat2.jpg        (you add this)
    ├── ucar.png          (you add this)
    ├── nadas_logo.png    (you add this)
    └── screens/          Real screenshots of the running application
```
