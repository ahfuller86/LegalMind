// legalmind-tools/src/index.ts

// This would be imported from the OpenClaw SDK normally
declare const api: {
    registerTool: (name: string, definition: any) => void;
};

const ENGINE_URL = "http://localhost:8000/api";

// Helper for making requests
async function callEngine(endpoint: string, method: string, data?: any) {
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
    } catch (error) {
        return { error: (error as Error).message };
    }
}

export function activate() {

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
        execute: async (args: any) => callEngine("/case/init", "POST", args)
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
        execute: async (args: any) => callEngine(`/case/status?case_id=${args.case_id}`, "GET")
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
        execute: async (args: any) => callEngine("/evidence/register", "POST", args)
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
        execute: async (args: any) => callEngine("/document/register", "POST", args)
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
        execute: async (args: any) => callEngine("/evidence/ingest", "POST", args)
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
        execute: async (args: any) => callEngine("/index/chunk", "POST", args)
    });

    api.registerTool("legalmind.index.build", {
        description: "Build/rebuild the dual retrieval index. Start/poll: returns run_id or status.",
        parameters: {
            type: "object",
            properties: {
                run_id: { type: "string" }
            }
        },
        execute: async (args: any) => callEngine("/index/build", "POST", args)
    });

    api.registerTool("legalmind.index.health", {
        description: "Return index health metrics and degradation flags.",
        parameters: { type: "object", properties: {} },
        execute: async (args: any) => callEngine("/index/health", "GET")
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
        execute: async (args: any) => callEngine("/brief/extract-claims", "POST", args)
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
        execute: async (args: any) => callEngine("/audit/run", "POST", args)
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
        execute: async (args: any) => callEngine("/retrieve/hybrid", "POST", args)
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
        execute: async (args: any) => callEngine("/verify/claim", "POST", args)
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
        execute: async (args: any) => callEngine("/citations/verify-batch", "POST", args)
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
        execute: async (args: any) => callEngine("/prefile/run", "POST", args)
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
        execute: async (args: any) => callEngine("/report/render", "POST", args)
    });
}
