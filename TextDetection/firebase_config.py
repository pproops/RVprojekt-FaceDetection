import pyrebase

config = {
    'apiKey': "AIzaSyCud6tanPgAQUSwvyJyuzubrPencLFqciA",
    'authDomain': "text-detection-app-c6172.firebaseapp.com",
    'projectId': "text-detection-app-c6172",
    'storageBucket': "text-detection-app-c6172.appspot.com",
    'messagingSenderId': "538556670304",
    'appId': "1:538556670304:web:0ebe430a85a59bbd57fe05",
    'databaseURL': " "
}

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()