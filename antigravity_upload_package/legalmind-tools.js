"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
// legalmind-tools/src/index.ts
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const os = __importStar(require("os"));
const adm_zip_1 = __importDefault(require("adm-zip"));
const ENGINE_URL = "http://localhost:8000/api";
// Helper for making requests
async function callEngine(endpoint, method, data) {
    try {
        const response = await fetch(`${ENGINE_URL}${endpoint}`, {
            method,
            headers: { "Content-Type": "application/json" },
            body: data ? JSON.stringify(data) : undefined,
        });
        if (!response.ok) {
            throw new Error(`Engine returned ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    }
    catch (error) {
        return { error: error.message };
    }
}
async function uploadFileToEngine(endpoint, filePath) {
    try {
        let fileToUploadPath = filePath;
        let isTemp = false;
        const stats = fs.lstatSync(filePath);
        if (stats.isDirectory()) {
            const zip = new adm_zip_1.default();
            zip.addLocalFolder(filePath);
            const zipName = `${path.basename(filePath)}.zip`;
            fileToUploadPath = path.join(os.tmpdir(), zipName);
            zip.writeZip(fileToUploadPath);
            isTemp = true;
        }
        const fileBuffer = fs.readFileSync(fileToUploadPath);
        const fileName = path.basename(fileToUploadPath);
        const formData = new FormData();
        const fileBlob = new Blob([fileBuffer]);
        formData.append("file", fileBlob, fileName);
        const response = await fetch(`${ENGINE_URL}${endpoint}`, {
            method: "POST",
            body: formData,
        });
        if (isTemp) {
            try {
                fs.unlinkSync(fileToUploadPath);
            }
            catch (e) { }
        }
        if (!response.ok) {
            throw new Error(`Engine returned ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    }
    catch (error) {
        return { error: error.message };
    }
}
function activate() {
    // --- Case & Evidence ---
    api.registerTool("legalmind.case.init", {
        description: "Initialize a new per-case workspace with isolated Engine stores.",
        parameters: {
            type: "object",
            properties: {
                case_name: { type: "string" }
            },
            required: ["case_name"]
        },
        execute: async (args) => callEngine("/case/init", "POST", args)
    });
    api.registerTool("legalmind.case.status", {
        description: "Return case manifest, index health, and degradation flags.",
        parameters: {
            type: "object",
            properties: {
                case_id: { type: "string" }
            },
            required: ["case_id"]
        },
        execute: async (args) => callEngine(`/case/status?case_id=${args.case_id}`, "GET")
    });
    api.registerTool("legalmind.evidence.upload", {
        description: "Upload a file or folder from the local filesystem to the Engine. Folders are automatically zipped. Returns the server-side file path.",
        parameters: {
            type: "object",
            properties: {
                file_path: { type: "string" }
            },
            required: ["file_path"]
        },
        execute: async (args) => uploadFileToEngine("/evidence/upload", args.file_path)
    });
    api.registerTool("legalmind.evidence.register", {
        description: "Register a file in the Evidence Vault with checksumming and integrity checks.",
        parameters: {
            type: "object",
            properties: {
                file_path: { type: "string" }
            },
            required: ["file_path"]
        },
        execute: async (args) => callEngine("/evidence/register", "POST", args)
    });
    api.registerTool("legalmind.document.register", {
        description: "Register a brief or filing as a document under audit.",
        parameters: {
            type: "object",
            properties: {
                file_path: { type: "string" }
            },
            required: ["file_path"]
        },
        execute: async (args) => callEngine("/document/register", "POST", args)
    });
    // --- Pipeline Operations (Start/Poll) ---
    api.registerTool("legalmind.evidence.ingest", {
        description: "Run conversion sub-pipeline. Start/poll: returns run_id or status + EvidenceSegment IDs.",
        parameters: {
            type: "object",
            properties: {
                file_path: { type: "string" },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/evidence/ingest", "POST", args)
    });
    api.registerTool("legalmind.index.chunk", {
        description: "Run the Structuring pipeline on EvidenceSegments. Returns Chunk IDs.",
        parameters: {
            type: "object",
            properties: {
                segment_ids: { type: "array", items: { type: "string" } },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/index/chunk", "POST", args)
    });
    api.registerTool("legalmind.index.build", {
        description: "Build/rebuild the dual retrieval index. Start/poll: returns run_id or status.",
        parameters: {
            type: "object",
            properties: {
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/index/build", "POST", args)
    });
    api.registerTool("legalmind.index.health", {
        description: "Return index health metrics and degradation flags.",
        parameters: { type: "object", properties: {} },
        execute: async (args) => callEngine("/index/health", "GET")
    });
    // --- Brief Audit ---
    api.registerTool("legalmind.brief.extract_claims", {
        description: "Extract and classify claims from a brief file. Returns Claim objects.",
        parameters: {
            type: "object",
            properties: {
                file_path: { type: "string" }
            },
            required: ["file_path"]
        },
        execute: async (args) => callEngine("/brief/extract-claims", "POST", args)
    });
    api.registerTool("legalmind.audit.run", {
        description: "Run full QC audit pipeline. Start/poll: returns run_id or status.",
        parameters: {
            type: "object",
            properties: {
                brief_path: { type: "string" },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/audit/run", "POST", args)
    });
    api.registerTool("legalmind.retrieve.hybrid", {
        description: "Execute hybrid retrieval for a claim. Returns EvidenceBundle.",
        parameters: {
            type: "object",
            properties: {
                claim_id: { type: "string" }
            },
            required: ["claim_id"]
        },
        execute: async (args) => callEngine("/retrieve/hybrid", "POST", args)
    });
    api.registerTool("legalmind.verify.claim", {
        description: "Run adversarial verification on a claim + evidence bundle. Returns VerificationFinding.",
        parameters: {
            type: "object",
            properties: {
                claim_id: { type: "string" },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/verify/claim", "POST", args)
    });
    api.registerTool("legalmind.citations.verify_batch", {
        description: "Run dual-pass citation verification on text. Returns CitationFindings.",
        parameters: {
            type: "object",
            properties: {
                text: { type: "string" },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/citations/verify-batch", "POST", args)
    });
    api.registerTool("legalmind.prefile.run", {
        description: "Run full Sentinel pre-filing pipeline. Start/poll: returns run_id or status + GateResult.",
        parameters: {
            type: "object",
            properties: {
                brief_path: { type: "string" },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/prefile/run", "POST", args)
    });
    api.registerTool("legalmind.report.render", {
        description: "Render report from findings. Start/poll: returns run_id or status + file path.",
        parameters: {
            type: "object",
            properties: {
                findings_ids: { type: "array", items: { type: "string" } },
                run_id: { type: "string" }
            }
        },
        execute: async (args) => callEngine("/report/render", "POST", args)
    });
}
