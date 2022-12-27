### Top-line Block
The following code block is the metadata to put on top of the .yaml files
```YAML
---
Title:
Description:
Metadata:
    Creator:
    Power Output:
    Output State:
    Output Handling:
    Recycling: 
---

```

### Classification
There are 4 types of lines classified by how much power they generate (Power Output):
- **None**: Does not generate sufficient power to matter
- **Partial**: Generates energy to power part of itself
- **Sufficient**: Generates enough energy to power itself
- **Significant**: Generates enough energy to power itself and others

There are 4 types of lines classified by what they mainly output in order of priority (Output State):
- **Hot**: Hot material that needs to be cooled
- **Dust**: Dusts for various uses
- **Fluid**: Fluids, may be gas or liquid
- **Energy**: Energy via any means
- **Item**: General item
- **Misc**: Anything else

There are 3 types of lines classified by how meticulous the outputs are (Output Handling):
- **None**: Only shows the relevant outputs
- **Partial**: Shows some but not all irrelevant outputs
- **Full**: Shows every single output
  
Lastly, there are 3 types of lines classified by amount of recycling (Recycling):
- **None**: Does not recycle outputs
- **Partial**: Recycles some outputs
- **Full**: Recycles all possible outputs

### Filenames
Here are some ways to format filenames:
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