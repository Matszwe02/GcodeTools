# Python G-Code Tools library with complete* G-Code Reader and Writer

\*as per 3D-Printing needs


# Available G-Code Tools

| Feature                        | Status |                command                 |
| ------------------------------ | :----: | :------------------------------------: |
| Translate Gcode                |   ✅   |       `gcode.translate(Vector)`        |
| Rotate Gcode                   |   ✅   |         `gcode.rotate(float) `         |
| Scale Gcode                    |   ✅   |         `gcode.scale(Vector)`          |
| Detect Gcode features          |  🔜   |     `GcodeTools.fill_meta(gcode)`      |
| Split layers                   |  🔜   |     `gcode.get_by_meta(str, Any)`      |
| Split bodies                   |  🔜   |       `GcodeTools.split(gcode)`        |
| Insert custom Gcode            |   ❌   |                                        |
| Generate Thumbnails            |   ❌   |                                        |
| Convert from/to Arc Moves      |   ❌   |                                        |
| Split bodies                   |   ❌   |                                        |
| Find body bounds               |   ✅   | `GcodeTools.get_bounding_cube(gcode)`  |
| Trim unused Gcode              |  🔜   |        `GcodeTools.trim(gcode)`        |
| Offset Gcodes in time          |   ❌   |                                        |
| Create custom travel movement  |   ❌   |                                        |
| convert to firmware retraction |  🔜   | `GcodeTools.regenerate_travels(gcode)` |


### Legend:

- ✅ Fully supported
- ❌ Not yet supported, to be implemented
- 🔜 Partially supported, to be implemented

# G-Code Parser

```py
from gcode import Gcode

gcode = Gcode()
# gcode.config.speed = ...
gcode.from_file('file.gcode')
```

## Progress Callback

```py
from gcode import Gcode
import tqdm

my_tqdm = tqdm(unit="lines", desc="Reading Gcode")
update = lambda i, length: (setattr(my_tqdm, 'total', length), my_tqdm.update(1))

gcode.from_file('file.gcode', update)
```


# Example usage

```py
from gcode_tools import Gcode, GcodeTools, Vector

do_verbose = False

gcode = Gcode()
gcode.config.speed = 1200

gcode.from_file('file.gcode')
meta_gcode: Gcode = GcodeTools.fill_meta(gcode)
out_gcode = GcodeTools.trim(meta_gcode)

translation = Vector(-200, -100, 0)

for x in out_gcode:
    obj: str = x.meta.get('object')
    if 'benchy' in obj.lower():
        x.translate(translation)

out_gcode.write_file('out.gcode', do_verbose)
```


# Supported Slicers

Tested with:
- Prusa Slicer `2.8.1`
- Orca Slicer `2.1.1`
- Super Slicer `2.5.59.12`
- Slic3r `1.3.0`
- Cura `5.8.1`
- Simplify3D `4.0.0`


|                           | Any slicer | Cura | Prusa&nbsp;Slicer | Orca&nbsp;Slicer | Slic3r | Super&nbsp;Slicer | Simplify3D |
| ------------------------- | :--------: | :--: | :---------------: | :--------------: | :----: | :---------------: | :--------: |
| Reading Gcode             |     ✅     |      |                   |                  |        |                   |            |
| Keep track of coordinates |     ✅     |      |                   |                  |        |                   |            |
| Temperature control       |     ✅     |      |                   |                  |        |                   |            |
| Fan control               |     ✅     |      |                   |                  |        |                   |            |
| Spliting Objects          |     ❌     |  ✅  |       ☑️1       |        ✅        |   ❌   |        ✅         |     ✅     |
| Extracting features       |     ❌     |  ➖  |        ✅         |        ✅        |   ❌   |        ✅         |     ✅     |
| Arc Moves                 |   ☑️2    |      |                   |                  |        |                   |            |


### Legend:

- ✅ Fully supported
- ❌ Not supported
- 🔜 Partially supported, to be implemented
- ➖ Partially supported, limited by slicer
- ☑️ Supported, with precautions:

  1: Turn on `LABEL_OBJECTS`\
  2: Arc moves currently automatically translate to G1 moves



More features soon!