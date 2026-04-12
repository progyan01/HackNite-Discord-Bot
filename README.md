
# Lost Wages

  

Welcome to the **Lost Wages** bot! A full-featured, high-stakes Las Vegas/Sin City themed Discord bot featuring a comprehensive economy, a gripping heist roleplay system, and multiple casino minigames.

  

##  Features

  

###  Dynamic Economy & Custom Profiles

-  **Robust Economy System**: Complete with daily streaks, balance tracking, loans, and bounties.

-  **Image Generation**: Dynamic user profiles generated on the fly using `Pillow`.

-  **Leaderboards**: Global leaderboards to track the wealthiest players in Sin City.

-  **Marketplace**: `/buy` perks and view your owned items via `/inventory`.

  

###  Casino Gambling

Put your chips on the line with fully interactive, high-stakes gambling minigames:

-  **Blackjack**: A premium blackjack game against a dealer with real card evaluations.

-  **Crash**: A real-time multiplier that ticks up dynamically! Will you cash out or let it crash?

-  **Slots**: A 3x3 slot machine with various payouts and symbols.

-  **Duels**: Challenge other players to a risk-filled duel (Rock-Paper-Scissors style  but with 5 Noir weapons).

-  *Bonus*: Earn random rare perk drops just by playing!

  

###  Heist Roleplay

Assemble a crew and go after the big scores!

-  **Multiple Targets**: Rob a Gas Station, a Jewelry Store, or go big for the Casino Vault.

-  **Crew Roles**: Assemble your team with specialized roles (Driver, Muscle, Hacker, Inside Man).

-  **Consumable Perks**: Use your 10%, 15%, or 20% boost perks (gained from the marketplace or gambling drops) to increase your success chance.

-  **Lobby Management**: Automated 2-minute timeouts for inactive lobbies.

  

##  Technology Stack

-  **Library**: `discord.py` >= 2.3.0

-  **Database**: `aiosqlite` for fast, asynchronous local data handling.

-  **Environment**: `python-dotenv` for token security.

-  **Image Processing**: `pillow` >= 10.0.0 for custom profile generation.

  

##  Setup & Installation

  

1.  **Clone the repository:**

```bash

git clone <repo-url>

cd hacknite-bot

```

  

2.  **Install dependencies:**

Make sure you are in your virtual environment and run:

```bash

pip install -r requirements.txt

```

  

3.  **Configure Environment Variables:**

Create a `.env` file in the root directory and add your Discord Bot Token:

```env

BOT_TOKEN=your_token_here

```

  

4.  **Run the Bot!**

```bash

python bot.py

```

  

##  Bot Commands Overview

Here are a few commands to get you started:

-  **Economy**: `/daily`, `/profile`, `/leaderboard`, `/buy`, `/inventory`

-  **Gambling**: `/blackjack`, `/crash`, `/slots`, `/duel`

-  **Heists**: `/heist start`, `/heist join`, `/heist launch`

  

*Note: All commands are implemented as Discord Slash Commands (`/`). Make sure your bot has the `application.commands` scope invited.*