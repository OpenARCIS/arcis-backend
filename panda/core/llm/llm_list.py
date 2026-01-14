MISTRAL_AI = [
    "codestral-2405",
    "codestral-2501",
    "codestral-mamba-2407",
    "ministral-3b-2410",
    "ministral-8b-2410",
    "mistral-embed",
    "mistral-large-2402",
    "mistral-large-2407",
    "mistral-large-2411",
    "mistral-medium",
    "mistral-moderation-2411",
    "mistral-saba-2502",
    "mistral-small-2402",
    "mistral-small-2409",
    "mistral-small-2501",
    "mistral-small-2503",
    "open-mistral-7b",
    "open-mistral-nemo",
    "open-mixtral-8x22b",
    "open-mixtral-8x7b",
    "pixtral-12b-2409",
    "pixtral-large-2411"
]

CEREBRAS = [
    "gpt-oss-120b",
    "llama-3.3-70b",
    "llama3.1-8b",
    "qwen-3-235b-a22b-instruct-2507",
    "qwen-3-32b",
    "zai-glm-4.6",
    "zai-glm-4.7"
]

GROQ = [
    "allam-2-7b",
    "canopylabs/orpheus-arabic-saudi",
    "canopylabs/orpheus-v1-english",
    "groq/compound",
    "groq/compound-mini",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-guard-4-12b",
    "meta-llama/llama-prompt-guard-2-22m",
    "meta-llama/llama-prompt-guard-2-86m",
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-instruct-0905",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-safeguard-20b",
    "qwen/qwen3-32b",
    "whisper-large-v3",
    "whisper-large-v3-turbo"
]

OPENROUTER_MODELS = {
    "allenai/molmo-2-8b:free": {
        "parameters": "8B",
        "context": "128k",
        "usage": "Video grounding & counting",
        "speed": "40 - 60 tps"
    },
    "xiaomi/mimo-v2-flash:free": {
        "parameters": "309B (15B active)",
        "context": "256k",
        "usage": "Production-grade agents; high-speed coding & math reasoning",
        "speed": "150+ tps"
    },
    "nvidia/nemotron-3-nano-30b-a3b:free": {
        "parameters": "32B (3.5B active)",
        "context": "1M",
        "usage": "Math reasoning & tool-use",
        "speed": "80 - 120 tps"
    },
    "mistralai/devstral-2512:free": {
        "parameters": "123B",
        "context": "256k",
        "usage": "Agentic software engineering",
        "speed": "15-25 tps"
    },
    "arcee-ai/trinity-mini:free": {
        "parameters": "26B (3B active)",
        "context": "128k",
        "usage": "Multi-step agent workflows",
        "speed": "100 - 150 tps"
    },
    "tngtech/tng-r1t-chimera:free": {
        "parameters": "671B (37B active)",
        "context": "131k",
        "usage": "Balanced reasoning; reduces verbose output by 40% vs R1",
        "speed": "15 - 20 tps"
    },
    "nvidia/nemotron-nano-12b-v2-vl:free": {
        "parameters": "12B",
        "context": "128k",
        "usage": "On-device vision-language",
        "speed": "45 - 70 tps"
    },
    "nvidia/nemotron-nano-9b-v2:free": {
        "parameters": "9B",
        "context": "128k",
        "usage": "Low-latency agentic tasks",
        "speed": "90 - 130 tps"
    },
    "openai/gpt-oss-120b:free": {
        "parameters": "120B",
        "context": "128k",
        "usage": "Open-source heavy reasoning",
        "speed": "10 - 18 tps"
    },
    "openai/gpt-oss-20b:free": {
        "parameters": "20B",
        "context": "128k",
        "usage": "Consumer-grade reasoning",
        "speed": "50 - 80 tps"
    },
    "z-ai/glm-4.5-air:free": {
        "parameters": "100B+ (MoE)",
        "context": "128k",
        "usage": "Balanced performance/speed",
        "speed": "30 - 50 tps"
    },
    "qwen/qwen3-coder:free": {
        "parameters": "30B - 480B",
        "context": "256k+",
        "usage": "Expert coding & repo analysis",
        "speed": "12 - 45 tps"
    },
    "moonshotai/kimi-k2:free": {
        "parameters": "1T (32B active)",
        "context": "128k",
        "usage": "Sequential tool calls/Thinking",
        "speed": "15 - 20 tps"
    },
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free": {
        "parameters": "24B",
        "context": "32k",
        "usage": "Uncensored creative writing",
        "speed": "40 - 65 tps"
    },
    "google/gemma-3n-e2b-it:free": {
        "parameters": "5B / 8B",
        "context": "32k",
        "usage": "Real-time on-device audio/video",
        "speed": "N/A"
    },
    "tngtech/deepseek-r1t2-chimera:free": {
        "parameters": "671B (37B active)",
        "context": "163k",
        "usage": "Advanced STEM reasoning; 2x faster than R1-0528",
        "speed": "20 - 30 tps"
    },
    "deepseek/deepseek-r1-0528:free": {
        "parameters": "671B (37B active)",
        "context": "128k",
        "usage": "SOTA mathematical reasoning",
        "speed": "10 - 25 tps"
    },
    "google/gemma-3n-e4b-it:free": {
        "parameters": "8B (3B memory)",
        "context": "32k",
        "usage": "Mobile Multimodal; real-time video/audio on edge",
        "speed": "80 - 120 tps"
    },
    "qwen/qwen3-4b:free": {
        "parameters": "4B",
        "context": "262k",
        "usage": "Local long-context; handling massive codebases on laptops",
        "speed": "120 - 160 tps"
    },
    "mistralai/mistral-small-3.1-24b-instruct:free": {
        "parameters": "24B",
        "context": "128k",
        "usage": "Enterprise-grade dialogue",
        "speed": "150+ tps"
    },
    "google/gemma-3-4b-it:free": {
        "parameters": "4B",
        "context": "128k",
        "usage": "Fast mobile vision tasks",
        "speed": "120+ tps"
    },
    "google/gemma-3-12b-it:free": {
        "parameters": "12B",
        "context": "128k",
        "usage": "Mid-range multimodal chat",
        "speed": "60 - 85 tps"
    },
    "google/gemma-3-27b-it:free": {
        "parameters": "27B",
        "context": "128k",
        "usage": "High-tier general multimodal",
        "speed": "30 - 45 tps"
    },
    "meta-llama/llama-3.3-70b-instruct:free": {
        "parameters": "70B",
        "context": "128k",
        "usage": "Reliable multilingual reasoning",
        "speed": "50 - 70 tps"
    },
    "meta-llama/llama-3.2-3b-instruct:free": {
        "parameters": "3B",
        "context": "128k",
        "usage": "Mobile summarization",
        "speed": "150+ tps"
    },
    "qwen/qwen-2.5-vl-7b-instruct:free": {
        "parameters": "7B",
        "context": "32k",
        "usage": "Visual grounding & OCR",
        "speed": "60 - 90 tps"
    },
    "nousresearch/hermes-3-llama-3.1-405b:free": {
        "parameters": "405B",
        "context": "128k",
        "usage": "Frontier-level open reasoning",
        "speed": "5 - 12 tps"
    },
    "meta-llama/llama-3.1-405b-instruct:free": {
        "parameters": "405B (Dense)",
        "context": "128k",
        "usage": "Enterprise foundation; synthetic data & complex translations",
        "speed": "5 - 12 tps"
    },
    "mistralai/mistral-7b-instruct:free": {
        "parameters": "7B",
        "context": "32k",
        "usage": "Lightweight general purpose",
        "speed": "90 - 110 tps"
    }
}

OPENAI = [
    "gpt-4o", 
    "gpt-4-turbo", 
    "gpt-3.5-turbo"
]

GEMINI = [
    "gemini-1.5-flash", 
    "gemini-1.5-pro", 
    "gemini-1.0-pro"
]

ANTHROPIC = [
    "claude-3-5-sonnet-20240620", 
    "claude-3-opus-20240229", 
    "claude-3-sonnet-20240229", 
    "claude-3-haiku-20240307"
]

OLLAMA = []

