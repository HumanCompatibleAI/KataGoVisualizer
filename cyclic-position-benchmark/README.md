This directory contains a script and SGF files for evaluating KataGo networks against various cyclic positions, based on [an original version](https://discord.com/channels/417022162348802048/459783732182777876/1079125236059996261) made by KataGo author David Wu.

Please note that this is not a conclusive, encompassing test for robustness, especially if considering only the overall averages. It can be used as an exploratory tool, as a preliminary indicator for performance in cyclic positions, or as one piece of evidence in a broader analysis. But better numbers here, on their own, do not guarantee a more robust model.


To use:

In `runcycletestsandplot.py`, set `PLOTS_PATH`, `SGFS_PATH`, `KATAGO_PATH`, and `MODELS_PATH` as desired. The first two can stay as default, `KATAGO_PATH` can probably stay as default (if you have set up the default container), `MODELS_PATH` will likely either need adjustment or copying of the desired models to the default directory. Note that a KataGo process will be called for every file in `MODELS_PATH`.

Adjust `get_model_name_for_plotting()` function if you need to change the automatic parsing of the default labels.


Adjust the config variables as desired.
