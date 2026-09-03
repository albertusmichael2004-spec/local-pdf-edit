import { initMediaTool } from "/frontend/assets/js/core/media_tool.js";

export function init() {
  initMediaTool({
    operation: "convert",
    ids: {
      input: "mediaConverterFiles", list: "mediaConverterList", target: "mediaConverterTarget",
      quality: "mediaConverterQuality", metadata: "mediaConverterMetadata", summary: "mediaConverterSummary",
      status: "mediaConverterStatus", clear: "clearMediaConverter", button: "runMediaConverter",
    },
  });
}
