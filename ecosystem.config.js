const os = require("os");
const isWin = os.platform() === "win32";

module.exports = {
  apps: [{
    name: "quantos",
    script: "main.py",
    cwd: __dirname,
    interpreter: isWin
      ? "C:\\Users\\josue\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe"
      : "./venv/bin/python3",
    watch: false,
    autorestart: true,
    max_restarts: 5,
    restart_delay: 10000,
    error_file: "./LOGS/pm2_error.log",
    out_file: "./LOGS/pm2_out.log",
    env: {
      PYTHONUNBUFFERED: "1"
    }
  }]
};
