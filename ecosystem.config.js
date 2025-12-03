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
        MONGO_URI: "mongodb://localhost:27017",
        OLLAMA_HOST: "http://localhost:11434"
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
