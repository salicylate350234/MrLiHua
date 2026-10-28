# Synthetic Demo / 合成演示

This folder contains a fully **synthetic** reading passage and two questions used only to demonstrate the interface.

- No real exam paper
- No school or student data
- No third-party answer key
- All content is invented for this repository

Build it with:

```powershell
python scripts/validate_exam.py examples/demo/demo_exam.json
python scripts/build_exam.py examples/demo/demo_exam.json -o examples/demo/demo_exam.html
```

Then open `demo_exam.html` in Microsoft Edge.
