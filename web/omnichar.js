// A colour for the CHARACTER socket, so a character wire is distinguishable from an image wire.
import { app } from "../../scripts/app.js";

app.registerExtension({
  name: "omnichar.character",
  init() {
    const types = app.canvas?.default_connection_color_byType;
    const links = LiteGraph.LINK_COLORS ?? {};
    const colour = "#c77dff";
    if (types) types["CHARACTER"] = colour;
    links["CHARACTER"] = colour;
  },
});
