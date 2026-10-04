#!/bin/bash
# Deployment script for Discord bot on Ubuntu VPS

echo "=== Discord Bot Deployment Script ==="
echo ""

# Update system
echo "1. Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip
echo "2. Installing Python and pip..."
sudo apt install -y python3 python3-pip git

# Install bot dependencies
echo "3. Installing Python dependencies..."
pip3 install -r requirements.txt

# Create database directory if it doesn't exist
echo "4. Setting up database directory..."
mkdir -p db

# Set up .env file (you'll need to edit this manually)
if [ ! -f .env ]; then
    echo "5. Creating .env template..."
    cat > .env << 'EOF'
DISCORD_TOKEN=your_discord_token_here
GOOGLE_SHEETS_CREDS=your_google_sheets_creds_here
BUDGET_SHEET_ID=your_budget_sheet_id_here
WEBSITE_URL=your_website_url_here
ANNIVERSARY_DATE=2025-08-02
PHOTOS_DIR=./photos
EOF
    echo "⚠️  IMPORTANT: Edit .env file with your actual credentials!"
else
    echo "5. .env file already exists, skipping..."
fi

# Copy systemd service file
echo "6. Setting up systemd service..."
sudo cp discord-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start the service
echo "7. Enabling and starting bot service..."
sudo systemctl enable discord-bot
sudo systemctl start discord-bot

echo ""
echo "=== Deployment Complete! ==="
echo ""
echo "Useful commands:"
echo "  Check bot status:  sudo systemctl status discord-bot"
echo "  View logs:         sudo journalctl -u discord-bot -f"
echo "  Restart bot:       sudo systemctl restart discord-bot"
echo "  Stop bot:          sudo systemctl stop discord-bot"
echo ""
echo "⚠️  Don't forget to:"
echo "  1. Edit the .env file with your actual Discord token"
echo "  2. Run the database setup if needed: python3 setup_db.py"
echo ""
