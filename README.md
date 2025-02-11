## 🍪 OPEN COOKIES FOLDER FOR MORE DETAILS ABOUT COOKIES.

## 🚀 Deploy on Heroku 
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?template=https://github.com/HerokuTaccc/acx)

---

### 🔧 Quick Setup [DEPLOY IN VPS]

1. **Upgrade & Update:**
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```

2. **Install Required Packages:**
   ```bash
   sudo apt-get install python3-pip ffmpeg -y
   ```
3. **Setting up PIP**
   ```bash
   sudo pip3 install -U pip
   ```
4. **Installing Node**
   ```bash
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.38.0/install.sh | bash && source ~/.bashrc && nvm install v18
   ```
5. **Clone the Repository**
   ```bash
   git clone https://github.com/HerokuTaccc/acx && cd acx
   ```
6. **Install Requirements**
   ```bash
   pip3 install -U -r requirements.txt
   ```
7. **Create .env  with sample.env**
   ```bash
   cp sample.env .env
   ```
   - Edit .env with your vars
8. **Editing Vars:**
   ```bash
   nano .env
   ```
   - Edit .env with your values.
   - Start editing.
   - Press `Ctrl + X` then `Y` then `ENTER` once you are done with editing vars. to exit without saving Press `Ctrl + X` then `N` then `ENTER`
9. **Installing tmux**
    ```bash
    sudo apt install tmux -y && tmux
    ```
10. **Run the Bot**
    ```bash
    bash start
    ```

---

### 🛠 Commands & Usage

The Aviax Music Bot offers a range of commands to enhance your music listening experience on Telegram:

| Command                 | Description                                 |
|-------------------------|---------------------------------------------|
| `/play <song name>`     | Play the requested song.                    |
| `/pause`                | Pause the currently playing song.           |
| `/resume`               | Resume the paused song.                     |
| `/skip`                 | Move to the next song in the queue.         |
| `/stop`                 | Stop the bot and clear the queue.           |
| `/queue`                | Display the list of songs in the queue.     |

For a full list of commands, use `/help` in [telegram](https://t.me/AviaxBeatzBot).

---

### 📜 License

This project is licensed under the MIT License. For more details, see the [LICENSE](LICENSE) file.

---

### 🙏 Acknowledgements

Thanks to all the contributors, supporters, and users of the Aviax Music Bot. Your feedback and support keep us going!
- [Yukki Music](https://github.com/TeamYukki/YukkiMusicBot) and [AnonXMusic](https://github.com/AnonymousX1025/AnonXMusic) For their Source Codes.
- **Special Thanks** to [SPiDER 🇮🇳](https://github.com/Surendra9123) for invaluable assistance in resolving the IP ban issue.
