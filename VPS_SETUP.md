# Ubuntu VPS Setup Guide for Discord Bot

## Step 1: SSH into your VPS

```bash
ssh root@your-vps-ip
# or
ssh your-user@your-vps-ip
```

## Step 2: Create a non-root user (optional but recommended)

```bash
adduser ubuntu
usermod -aG sudo ubuntu
su - ubuntu
```

## Step 3: Clone the bot

```bash
cd /home/ubuntu
git clone https://github.com/scottprints/new-bot.git
cd new-bot
```

## Step 4: Run the deployment script

```bash
chmod +x deploy.sh
./deploy.sh
```

## Step 5: Configure environment variables

```bash
nano .env
```

Add your credentials:
```
DISCORD_TOKEN=your_discord_token_here
GOOGLE_SHEETS_CREDS=your_google_sheets_creds_here
BUDGET_SHEET_ID=your_budget_sheet_id_here
WEBSITE_URL=your_website_url_here
ANNIVERSARY_DATE=2025-08-02
PHOTOS_DIR=./photos
```

Save: `Ctrl+X`, then `Y`, then `Enter`.

## Step 6: Set up the database

```bash
python3 setup_db.py
```

## Step 7: Start the bot

```bash
sudo systemctl start discord-bot
sudo systemctl status discord-bot
```

## Common Commands

| Action | Command |
|--------|---------|
| Check status | `sudo systemctl status discord-bot` |
| View logs | `sudo journalctl -u discord-bot -f` |
| Restart bot | `sudo systemctl restart discord-bot` |
| Stop bot | `sudo systemctl stop discord-bot` |
| View last 50 log lines | `sudo journalctl -u discord-bot -n 50` |

## Updating the bot

```bash
cd /home/ubuntu/new-bot
git pull
sudo systemctl restart discord-bot
```

## Auto-restart monitoring (optional)

```bash
crontab -e
# Add this line to check every 5 minutes:
*/5 * * * * systemctl is-active --quiet discord-bot || systemctl start discord-bot
```

## Troubleshooting

### Bot won't start
```bash
sudo journalctl -u discord-bot -n 100
cat .env
python3 bot.py  # test manually
```

### Permission issues
```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/new-bot
ls -la db/
```

### Firewall (if bot needs port 5000 for Flask API)
```bash
sudo ufw allow 5000/tcp
sudo ufw enable
```