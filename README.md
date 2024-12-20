# Goals
Bot for swewerver

### Warn System
  - [X] Warn user
  - [X] Persistent database for storing warns
  - [X] CRUD Warns
---
### Verify 18+ system
  - [X] Verify user
  - [X] Gives user role
  - [X] Add verification to database
  - [X] Check verification command
  - [X] Delete verification
  - [X] Check verification command gives back verified role if not present (due to user leaving or something)
  - [X] Deleted verification also removes verified role from user
---
### Tag system
  - [X] Prints frequently needed messages
  - [X] CRUD Tags
---
### Mod Actions
  - [X] Log all important actions in a specified channel
  - [X] Show who and timestamp when action was taken.
---
### Mute System
  - [X] Mute command
  - [X] Unmute command
  - [X] Saves users roles/removes all their roles and gives them the MUTED role
  - [X] Must not work with users who have a role above or same as their own role
  - [X] Takes parsed duration inputs (10s for 10 seconds, 10m for 10 minutes, 10h for 10 hours)
---
### Ban System
  - [X] Ban users
  - [X] Unban users
  - [X] Be able to customize the msg they get when being banned
  - [X] Can't ban users above or same as their role
  - [X] Ban users by userID (can ban users not in the server)
---
### Ticket System (Optional)
  - [ ] Drop down to select different types of tickets
  - [ ] Customize each type of ticket to print a different embed
  - [ ] Close/Open/Delete ticket buttons with customizable perms
  - [ ] On open/close/claim moves to a selected category
  - [ ] Force verify command, mutes them and adds to verify ticket. (Prolly a command to select what ticket that is)
---
### Database
  - [X] Ban Table
  - [X] Mute Table
  - [X] Warn Table
  - [X] Verify Table
  - [X] Tag Table
  - [X] Mod-Actions Table
  - [X] Tickets Table
  - [X] Roles Backup Table
---
### Misc
  - [X] Users that have left the server have their roles restored
  - [X] Detects unusual amount of text in a short time, mutes offenders etc, maybe put into slow-mode if multiple users
---
### Additional Features
  - [X] Bot Details Command: Provides information about the bot, including ping and server name.
  - [X] Anti-Spam Logic: Detects and mutes users for excessive messaging and enables slow mode if multiple users spam.
  - [X] Role Backup and Restore: Saves and restores user roles when they leave and rejoin the server.
---
# Dependencies
- `discord.py`: For interacting with the Discord API.
- `python-dotenv`: For loading environment variables.
- `sqlite3`: For database operations.
- `asyncio`: For asynchronous operations.
- `logging`: For logging events and errors.
