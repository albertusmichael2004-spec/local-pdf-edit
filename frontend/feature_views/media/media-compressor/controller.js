import { initMediaTool } from "/frontend/assets/js/core/media_tool.js";
import { $$ } from "/frontend/assets/js/core/dom.js";

export function init() {
  $$("input[name='mediaCompressionMode']").forEach((radio) => {
    radio.addEventListener("change", () => {
      $$("#mediaCompressionProfiles .profile").forEach((profile) => {
        profile.classList.toggle("selected", profile.contains(radio));
      });
    });
  });
  initMediaTool({
    operation: "compress",
    ids: {
      input: "mediaCompressorFiles", list: "mediaCompressorList", target: "mediaCompressorTarget",
      qualityName: "mediaCompressionMode", metadata: "mediaCompressorMetadata", summary: "mediaCompressorSummary",
      status: "mediaCompressorStatus", clear: "clearMediaCompressor", button: "runMediaCompressor",
    },
  });
}
