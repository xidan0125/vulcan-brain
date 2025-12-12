module.exports = {
  apps: [
    {
      name: "vulcan-backend",
      script: "./venv/bin/python",
      args: "-m uvicorn api_server:app --host 0.0.0.0 --port 8001",
      cwd: "/home/xinyue/vulcan-brain",
      autorestart: true,
      watch: false,
      max_memory_restart: "4G",
      env: {
        // JWT
        JWT_SECRET: "vulcan_brain_secret_2024_prod",
        
        // MongoDB
        MONGO_URI: "mongodb://localhost:27017",
        
        // Feishu (Project Manager Bot)
        FEISHU_APP_ID: "cli_a9a255eeb278de1a",
        FEISHU_APP_SECRET: "t7lIdQLoRywiSyslQL4N4G8Pr0PmwGWk",
        
        // Feishu (Brain AI Bot)
        FEISHU_BRAIN_APP_ID: "cli_a9a3995b80389e1a",
        FEISHU_BRAIN_APP_SECRET: "zvvISVIsW4YwEbj9rTJhccYZnZCjfmFN",
        
        // LLM
        LLM_MODEL_NAME: "qwen3:30b-a3b",
        LLM_BASE_URL: "http://localhost:11434",
        OLLAMA_HOST: "http://localhost:11434",
        
        // Microsoft 365
        MS365_CLIENT_ID: "675bcdcf-19da-4700-9ccf-889dbe2d1239",
        MS365_TENANT_ID: "f7f20c78-407d-4ec2-bb4a-67f3b3ab26b7",
        MS365_CLIENT_SECRET: "uEo8Q~nIjfE2RU5xykw7V_sNqX4ao.QG1.z_icZ5"
      }
    },
    {
      name: "vulcan-frontend",
      script: "npm",
      args: "start",
      cwd: "/home/xinyue/vulcan-brain/vulcan-ui",
      interpreter: "/home/xinyue/.nvm/versions/node/v20.19.6/bin/node",
      autorestart: true,
      watch: false,
      env: {
        PORT: 3000,
        NODE_ENV: "production"
      }
    }
  ]
};
