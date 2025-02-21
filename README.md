# Python G-Code Tools library with complete* G-Code Reader and Writer

\*as per 3D-Printing needs


**This library is under development - method names, workflow and logic will differ between releases!**

**Ensure your printer software can catch illegal g-code moves, as this library has still very large amount of bugs! Also keep an eye on your print.**

# Installation

```sh
pip install GcodeTools
```

# Available G-Code Tools

| Feature                                              | Status |                                command                                 |
| ---------------------------------------------------- | :----: | :--------------------------------------------------------------------: |
| Translate Gcode                                      |   ✅   |                 `GcodeTools.translate(gcode, Vector)`                  |
| Rotate Gcode                                         |   ✅   |                    `GcodeTools.rotate(gcode, int) `                    |
| Scale Gcode                                          |   ✅   |                `GcodeTools.scale(gcode, Vector\|float)`                |
| subdivide Gcode                                      |   ✅   |                      `move.subdivide(prev, step)`                      |
| Get move's flowrate                                  |   ✅   |                       `move.get_flowrate(prev)`                        |
| Set flowrate <br> (in mm^2, use `scale` to set in %) |   ✅   |                    `move.set_flowrate(prev, float)`                    |
| Detect Gcode features                                |   ✅   |  `GcodeTools.fill_meta(gcode)`, option `meta_provider` at gcode load   |
| Split layers                                         |  🔜   |                     `gcode.get_by_meta(str, Any)`                      |
| Split bodies                                         |  🔜   |                       `GcodeTools.split(gcode)`                        |
| Insert custom Gcode                                  |   ❌   |                                                                        |
| Read Thumbnails                                      |   ✅   |                   `GcodeTools.get_thumbnails(gcode)`                   |
| Generate Thumbnails                                  |   ✅   | `GcodeTools.generate_thumbnail(gcode, data, width, height, textwidth)` |
| Convert from/to Arc Moves                            |   ❌   |                                                                        |
| Find body bounds                                     |   ✅   |                 `GcodeTools.get_bounding_cube(gcode)`                  |
| Trim unused Gcode                                    |  🔜   |                        `GcodeTools.trim(gcode)`                        |
| Offset Gcodes in time                                |   ❌   |                                                                        |
| Create custom travel movement                        |   ❌   |                                                                        |
| convert to firmware retraction                       |  🔜   |                 `GcodeTools.regenerate_travels(gcode)`                 |


### Legend:

- ✅ Fully supported
- ❌ Not yet supported, to be implemented
- 🔜 Partially supported, to be implemented

More features soon! Feel free to open feature request


# G-Code

## Current G-Code object relation:
```
Gcode (list[Block])
│
├─ slicing config: Config
│
├─ single Gcode instruction: Block
│  │
│  ├─ Object handling everything move-related: Move
│  │  ├─ Position: Vector
│  │  └─ speed: float
│  │
│  ├─ Everything G-code related other than position: BlockData
│  └─ Slicer-specific features (meta): dict
└─ ...
```

In each block, every G-Code variable is contained. That means, blocks can be taken out of Gcode, rearranged, etc.

That however does not take move origin (move starting position) in count! `regenerate_travels` will be able to handle that in future.


# G-Code Parser

```py
from GcodeTools import Gcode

gcode = Gcode()
gcode.from_file('file.gcode')
```

## Progress Callback example implementation

```py
my_tqdm = tqdm(unit="lines", desc="Reading Gcode")
update = lambda i, length: (setattr(my_tqdm, 'total', length), my_tqdm.update(1))
gcode = Gcode().from_file('file.gcode', update)
```


# Example usage

Example to move objects that have `benchy` in their name, by `translation` vector.
```py
from GcodeTools import Gcode, GcodeTools, Vector

do_verbose = False

gcode = Gcode()
gcode.config.speed = 1200 # initial speed before first Gcode's `F` parameter

gcode.from_file('file.gcode', meta_provider=GcodeTools.fill_meta)
out_gcode: Gcode = GcodeTools.trim(gcode)

translation = Vector(-200, -100, 0)

for x in out_gcode:
    obj: str = x.meta.get('object')
    if 'benchy' in obj.lower():
        x.move.translate(translation)
out_gcode = GcodeTools.regenerate_travels(out_gcode)

out_gcode.write_file('out.gcode', do_verbose)
```


Change tool to `T1` when printing sparse infill, otherwise change to `T0`.
For bridges set fan speed to 100%.
```py
from GcodeTools import *

gcode = Gcode().from_file('file.gcode')

for block in gcode:
    if block.meta.get('type') == MoveTypes.SPARSE_INFILL:
        block.block_data.set_tool(1)
    else:
        block.block_data.set_tool(0)
    
    if block.meta.get('type') == MoveTypes.BRIDGE:
        block.block_data.set_fan(255)

gcode.write_file('out.gcode')
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
| Spliting Objects          |     ❌     |  ✅  |       ✅1       |        ✅        |   ❌   |        ✅         |     ✅     |
| Extracting features       |     ❌     |  ➖  |        ✅         |        ✅        |   ❌   |        🔜         |     ✅     |
| Arc Moves                 |   🔜2    |      |                   |                  |        |                   |            |


### Legend:

1: Turn on `LABEL_OBJECTS`\
2: Arc moves currently automatically translate to G1 moves

- ✅ Fully supported
- ❌ Not supported, limited by slicer
- 🔜 To be implemented
- ➖ Partially supported, limited by slicer