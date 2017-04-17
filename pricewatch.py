# Python 3.4.3
# virtualenv
#   beautifulsoup4 (4.5.1)
#   lxml (3.6.4)
#   pip (8.1.2)
#   setuptools (26.0.0)
#   wheel (0.29.0)

#           Database Design
#     __________         __________
#    |          |       |          |
#    |   game   |1----m*|  price   |
#    |__________|       |__________|
#
#     *gameId             *priceId
#      gameTitle           price
#      gameStore           priceTime
#                          priceDate
#                          gameId#


from bs4 import BeautifulSoup
from urllib import request
import sqlite3
import sys
import threading


def createConnection():
    conn = sqlite3.connect('games.db')
    c = conn.cursor()
    return conn, c


def createDatabase():
    conn, c = createConnection()
    c.execute('''
                CREATE TABLE IF NOT EXISTS game(
                    gameId INTEGER PRIMARY KEY AUTOINCREMENT,
                    gameTitle TEXT,
                    gameStore TEXT,
                    CONSTRAINT unique_only UNIQUE(gameTitle, gameStore));''')

    c.execute('''
                CREATE TABLE IF NOT EXISTS price(
                    priceId INTEGER PRIMARY KEY AUTOINCREMENT,
                    price TEXT,
                    priceTime TEXT,
                    priceDate TEXT,
                    priceAvailable TEXT,
                    gameId TEXT,
                    FOREIGN KEY(gameId) REFERENCES game(gameId));''')

    conn.commit()
    conn.close()


def makeSoup(url):
    html = request.urlopen(url)
    soup = BeautifulSoup(html, 'html.parser')
    return soup


def get_ozgameshop():
    print("updating PS4 game prices from ozgameshop.com .....")
    store = 'ozgameshop.com'
    gamedata = {}
    gamelist = []
    for page in range(1, 25):

        soup = makeSoup('http://www.ozgameshop.com/ps4-games/sort-most-popular/display-table/100-per-page/page-' + str(page))

        # loop until no results
        try:
            if "no results found" in soup.find(class_='catpagetext').text:
                break
        except:
            for game_id, game in enumerate(soup.find_all('tr')):
                for key, data in enumerate(game.find_all('td')):
                    # assign key names to the values
                    if key is 0:
                        keyName = 'title'
                    elif key is 2:
                        keyName = 'price'
                    elif key is 4:
                        keyName = 'stock'
                    else:
                        keyName = None

                    # update the gamedata
                    if keyName is not None:
                        gamedata.update({keyName: data.text})
                # add game data to the list
                gamelist.append(gamedata.copy())
    # printList(gamelist)
    saveData(gamelist, store)
    print("ozgameshop.com udpate complete!")
    return gamelist


def get_gamesmen():
    print("updating PS4 game prices from gamesmen.com.au .....")
    store = 'gamesmen.com.au'
    gamedata = {}
    gamelist = []
    soup = makeSoup('https://www.gamesmen.com.au/ps4/games/view-all/show/all')

    products = soup.find(class_='category-products')

    for games in products.find_all('ul'):
            for game in games.find_all(class_='item'):
                price = game.find(class_='price').text
                title = game.find(class_='product-name').text
                stock = game.find(class_='stock-availability').text
                gamedata = {'price': price.strip(),
                            'title': title,
                            'stock': stock}
                gamelist.append(gamedata)
    # printList(gamelist)
    saveData(gamelist, store)
    print("gamesmen.com.au udpate complete!")
    return gamelist


def downloadData():
    # Run two separate download threads
    ozgameshop_t = threading.Thread(target=get_ozgameshop, args=())
    gamesmen_t = threading.Thread(target=get_gamesmen, args=())
    ozgameshop_t.start()
    gamesmen_t.start()


def saveData(gamelist, store):
    conn, c = createConnection()
    for i in range(1, len(gamelist)):
        price = gamelist[int(i)]['price']
        stock = gamelist[int(i)]['stock']
        title = gamelist[int(i)]['title']

        # Insert a game and store to the game table
        c.execute("INSERT OR IGNORE INTO game(gameTitle, gameStore) VALUES (?, ?);", [title, store])

        # Get gameId for use as foriegn key constraint
        c.execute("SELECT gameId FROM game WHERE (gameTitle = ? AND gameStore = ?)", [title, store])
        gameId = c.fetchone()[0]

        # Save the price data to the price table
        c.execute('''
                    INSERT INTO price(
                        price,
                        priceTime,
                        priceDate,
                        priceAvailable,
                        gameId)
                    VALUES (
                        ?,
                        strftime('%H:%M', datetime('now', 'localtime')),
                        strftime('%d/%m/%Y', datetime('now', 'localtime')),
                        ?,
                        ?);''',
                  [price, stock, gameId])

    # Save (commit) the changes
    conn.commit()
    conn.close()


def getHistory(gameId):
    conn, c = createConnection()
    c.execute("SELECT  priceDate, priceTime, price, priceAvailable FROM price WHERE (gameId = ?)", [gameId])
    prices = c.fetchall()
    c.execute("SELECT gameTitle, gameStore FROM game WHERE (gameId = ?)", [gameId])
    game = c.fetchone()
    conn.close()
    return prices, game


def getSearch(query):
    conn, c = createConnection()
    query = '%' + query + '%'
    c.execute('''
                SELECT DISTINCT
                    game.gameId,
                    gameTitle,
                    gameStore,
                    price,
                    priceAvailable
                FROM price JOIN game
                ON price.gameId = game.gameId
                WHERE (game.gameTitle like ?)
                ORDER BY price.priceAvailable, CAST(REPLACE (price, '$', '') as decimal)''',
              [query])

    searchResults = c.fetchall()
    conn.close()
    return searchResults


def displayList(headings, records):
    try:
        if len(headings) == len(records[0]):
            maxChars = getMaxChars(records)

            hLine = '-' * int((sum(maxChars)) + (len(headings) * 7) + 1)
            print(hLine)  # ---------------------------------
            print('|', end='')
            for i, heading in enumerate(headings):
                space = ' ' * (maxChars[i] - len(heading))
                print(' ', heading, space, '     |', end='', sep='')
            print('')
            print(hLine)  # --------------------------------
            for record in records:
                print('|', end='')
                for i, item in enumerate(record):
                    space = ' ' * (maxChars[i] - len(str(item)))
                    print(' ', item, space, '     |', end='', sep='')
                print('')
            print(hLine)  # --------------------------------
            print('| showing', len(records), 'records. |\n')
        else:
            print("fields for headings and records don't match")
    except:
        print("No records found!  :(")


def getMaxChars(records):
    # get max chars for each column
    maxChars = []
    for i in range(0, len(records[0])):
        maxChars.append(max(len(str(r[i])) for r in records))
    return maxChars


########################################################################
#                           Start Main                                 #
########################################################################


print("\nWelcome to PS4 Game Price Watch\n")

createDatabase()

# Clean the argument input
argv1 = None
argv2 = None
try:
    argv1 = sys.argv[1]
    argv2 = sys.argv[2]
except:
    pass

# Filter through the users argument inputs
if argv1 == 'search' and argv2 is not None:
    try:
        headings = ['#', 'Name', 'Store', 'Price', 'Stock']
        games = getSearch(argv2)
        displayList(headings, games)
    except:
        print("Enter the right syntax!")

elif argv1 == 'history' and argv2 is not None:
    try:
        headings = ['Date', 'Time', 'Price', 'Stock']
        prices, game = getHistory(argv2)
        print('\nShowing history for "', game[0], '", from ', game[1], sep='')
        displayList(headings, prices)
    except:
        print("Game ID not found!  :(")

elif argv1 == 'update':
    downloadData()

else:
    print("usage:\n      update: (python pricewatch.py update)  - Run first to update the database with the latest games and prices\n      search: (python pricewatch.py search widget)\n     history: (python pricewatch.py history 22)")
