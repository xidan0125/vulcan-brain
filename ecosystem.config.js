module.exports = {
  apps: [
    {
      name: "vulcan-backend",
      script: "./venv/bin/python",
      args: "-m uvicorn api_server:app --host 0.0.0.0 --port 8001",
      cwd: "/home/xinyueyu/vulcan_brain_v2",
      autorestart: true,
      watch: false,
      max_memory_restart: "2G",
      env: {
        MONGO_URI: "mongodb://localhost:27017"
      }
    },
    {
      name: "vulcan-frontend",
      script: "npm",
      args: "start",
      cwd: "/home/xinyueyu/vulcan_brain_v2/vulcan-ui",
      autorestart: true,
      watch: false,
      env: {
        PORT: 3000,
        NODE_ENV: "production"
      }
    }
  ]
};
