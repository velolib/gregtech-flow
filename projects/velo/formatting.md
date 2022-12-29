## YAML Header
The following code block is the header YAML document to put on top. This is not required for the program to run.
```YAML
---
title:
description:
metadata:
    creator:
    power output:
    output state:
    output handling:
    recycling: 
---

```


### Accepted Values
These are the accepted values for **Power Output**:
- **None**: Does not generate sufficient power to matter
- **Partial**: Generates energy to power part of itself
- **Sufficient**: Generates enough energy to power itself
- **Significant**: Generates energy as its main function

These are the accepted values for **Output State**:
- **Hot**: Hot material that needs to be cooled
- **Dust**: Dusts for various uses
- **Fluid**: Fluids, may be gas or liquid
- **Energy**: Energy via any means
- **Item**: General item
- **Misc**: Anything else

These are the accepted values for **Output Handling**:
- **None**: Only shows the relevant outputs
- **Partial**: Shows some but not all irrelevant outputs
- **Full**: Shows every single output
  
These are the accepted values for **Recycling**:
- **None**: Does not recycle outputs
- **Partial**: Recycles some outputs
- **Full**: Recycles all possible outputs

## Filenames
Here are some standards to format filenames:
- **Output**  
The filename is just the main output, simple as.  
Example: epoxid.yaml, ptfe.yaml
- **Input-Output**  
Shows what the main input and output is, mainly used for simple processing lines.  
Example: rutile-titanium.yaml, scheelite-tungsten.yaml
- **Special_Output**  
Used for more notable lines, shows what makes it special.  
Example: tgsless_benzene.yaml, renewable_aluminium.yaml
- **Proc_Output**  
Only used for complicated processing lines  
Example: proc_platinum.yaml, proc_monazite.yaml

## Why format like this?
This formatting is used to increase readability of information in projects without needing to dive deep into the document or having to generate the graph.