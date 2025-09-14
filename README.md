# Python G-Code Tools library with complete* G-Code Reader and Writer

\*as per 3D-Printing needs


**This library is under development - method names, workflow and logic will differ between releases!**

**Ensure your printer software can catch illegal g-code moves, as this library has still very large amount of bugs! Also keep an eye on your print.**

# Installation

```sh
pip install GcodeTools
```

# Available G-Code Tools

| Feature                                              | Status |                            command                             |
| ---------------------------------------------------- | :----: | :------------------------------------------------------------: |
| Translate Gcode                                      |   ✅   |                `Tools.translate(gcode, Vector)`                |
| Rotate Gcode                                         |   ✅   |                  `Tools.rotate(gcode, int) `                   |
| Scale Gcode                                          |   ✅   |              `Tools.scale(gcode, Vector\|float)`               |
| subdivide Gcode                                      |   ✅   |                     `move.subdivide(step)`                     |
| Get move's flowrate                                  |   ✅   |                     `move.get_flowrate()`                      |
| Set flowrate <br> (in mm^2, use `scale` to set in %) |   ✅   |                   `move.set_flowrate(float)`                   |
| Detect Gcode features                                |   ✅   | `Tools.fill_meta(gcode)`, param `meta_provider` at gcode load  |
| Split layers                                         |   ✅   |                       `Gcode.layers[n]`                        |
| Split bodies                                         |  🔜   |                      `Tools.split(gcode)`                      |
| Insert custom Gcode                                  |   ✅   |           `Gcode.(insert, append, extend, __add__)`            |
| Read Thumbnails (raw PNG data)                       |   ✅   |                 `Tools.read_thumbnails(gcode)`                 |
| Write Thumbnails (raw PNG data)                      |   ✅   | `Tools.write_thumbnail(gcode, data, width, height, textwidth)` |
| Generate configuration files for slicer              |   ✅   |              `Tools.generate_config_files(gcode)`              |
| Convert from/to Arc Moves                            |   ❌   |        currently auto-translation to G1 in GcodeParser         |
| Find body bounds                                     |   ✅   |                `Tools.get_bounding_box(gcode)`                 |
| Trim unused Gcode                                    |  🔜   |                      `Tools.trim(gcode)`                       |
| Offset Gcodes in time                                |   ❌   |                                                                |
| Create custom travel movement                        |   ❌   |                                                                |
| convert to firmware retraction                       |  🔜   |               `Tools.regenerate_travels(gcode)`                |


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
├─ slicing config (precision, speed): Config
│
├─ single Gcode instruction: Block
│  │
│  ├─ Object handling everything move-related: Move
│  │  ├─ Position: Vector
│  │  └─ speed: float
│  │
│  ├─ Every other standard G-code: BlockData
│  ├─ Slicer-specific features (meta) (non-standarized, one may set their own custom meta provider method): dict
│  └─ Original command and if it's to be emitted: command, emit_command
└─ ...
```

In each block, every G-Code variable is contained. That means, blocks can be taken out of Gcode, rearranged, etc.

That however does not take move origin (move starting position) in count! That will be adressed in future.

`Gcode` structure and its components will be changing heavily during beta!
- Current target is to get rid of original command (work on trimmed `Gcode`) to decrease RAM usage and computation time
- Gcode is in the first tests of linked-list approach for simplification of iterating methods


# G-Code Parser

```py
from GcodeTools import Gcode

gcode = Gcode('file.gcode')
```

## Progress Callback example implementation

```py
my_tqdm = tqdm(unit="lines", desc="Reading Gcode")
update = lambda i, length: (setattr(my_tqdm, 'total', length), my_tqdm.update(1))
gcode = Gcode().from_file('file.gcode', update)
```


# Example usage

Example to move objects that have `benchy` in their name, by `translation` vector. It will also trim gcode (minify).
```py
from GcodeTools import Gcode, Tools, Vector

do_verbose = False

gcode = Gcode()
gcode.config.speed = 1200 # initial speed before first Gcode's `F` parameter

gcode.from_file('file.gcode')
out_gcode: Gcode = Tools.trim(gcode)

translation = Vector(-200, -100, 0)

for x in out_gcode:
    obj: str = x.meta.get('object') or ''
    if 'benchy' in obj.lower():
        x.move.translate(translation)

out_gcode.write_file('out.gcode', do_verbose)
```


Change tool to `T1` when printing sparse infill, otherwise change to `T0`.
For bridges set fan speed to 100%.
```py
from GcodeTools import *

gcode = Gcode('file.gcode')

for block in gcode:
    if block.meta.get('type') == MoveTypes.SPARSE_INFILL:
        block.block_data.set_tool(1)
    else:
        block.block_data.set_tool(0)
    
    if block.meta.get('type') == MoveTypes.BRIDGE:
        block.block_data.set_fan(255)

gcode.write_file('out.gcode')
```


Plot histogram of flow ratios. Useful for checking arachne settings.

```py
from GcodeTools import Gcode
import matplotlib.pyplot as plt

gcode_file = "1.gcode"

gcode = Gcode(gcode_file)

flowrates = []
for block in gcode:
    if flowrate := block.move.get_flowrate():
        flowrates.append(flowrate)

plt.figure(figsize=(12, 6))
plt.hist(flowrates, bins=100)
plt.xlabel("Flowrate (mm E / mm XYZ)")
plt.ylabel("Frequency")
plt.title(f"Flowrate Distribution for {gcode_file}")
plt.grid(axis='y', alpha=0.75)
plt.show()
plt.close()
```


Generate configuration files for slicer

```py
gcode = GcodeTools.Gcode('gcode.gcode')

config = Tools.generate_config_files(gcode)
for key in config.keys():
    with open(key, 'w') as f:
        f.write(config[key])
```


# Supported Slicers

Tested with:
- Prusa Slicer `2.8.1`
- Orca Slicer `2.1.1`
- Super Slicer `2.5.59.12`
- Slic3r `1.3.0`
- Cura `5.8.1`
- Simplify3D `4.0.0`
- Bambu Studio `2.0.3.54`


|                           | Any slicer | Cura | Prusa&nbsp;Slicer | Orca&nbsp;Slicer | Slic3r | Super&nbsp;Slicer | Simplify3D | Bambu&nbsp;Studio |
| ------------------------- | :--------: | :--: | :---------------: | :--------------: | :----: | :---------------: | :--------: | :----------: |
| Reading Gcode             |     ✅     |      |                   |                  |        |                   |            |              |
| Keep track of coordinates |     ✅     |      |                   |                  |        |                   |            |              |
| Temperature control       |     ✅     |      |                   |                  |        |                   |            |              |
| Fan control               |     ✅     |      |                   |                  |        |                   |            |              |
| Spliting Objects          |     ❌     |  ✅  |        ✅1        |        ✅        |   ❌   |        ✅         |     ✅     |     ✅      |
| Extracting features       |     ❌     |  ➖  |        ✅         |        ✅        |   ❌   |        ✅        |     ✅     |      ✅      |
| Arc Moves                 |    🔜2    |      |                   |                  |        |                   |            |              |


### Legend:

1: Turn on `LABEL_OBJECTS`\
2: Arc moves currently automatically translate to G1 moves

- ✅ Fully supported
- ❌ Not supported, limited by slicer
- 🔜 To be implemented
- ➖ Partially supported, limited by slicer