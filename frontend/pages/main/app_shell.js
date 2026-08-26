import { bindGlobalDropGuard } from "/frontend/assets/js/core/dropzones.js";
import { bindNavigation, showFeature } from "/frontend/assets/js/core/feature_loader.js";
import { loadHealth } from "/frontend/assets/js/core/health.js";

bindGlobalDropGuard();
bindNavigation();
loadHealth();
showFeature("merge");
