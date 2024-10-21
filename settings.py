# settings.py

API_KEY = 'AIzaSyAfZQXTcM3A9sfytozJftI9ZSk00jmd9jE'

PORTS = {
    'Bailey': 10000,
    'Bona': 10001,
    'Campbell': 10002,
    'Clark': 10003,
    'Jaquez': 10004,
}

neighbors = {
    'Bailey': ['Bona', 'Campbell'],
    'Bona': ['Bailey', 'Clark', 'Campbell'],
    'Campbell': ['Jaquez', 'Bona', 'Bailey'],
    'Clark': ['Jaquez', 'Bona'],
    'Jaquez': ['Clark', 'Campbell'],
}

clients = {

}