# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
import io
import pickle
import random
import time

import piexif
import piexif.helper
import requests
import yaml
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PIL import Image as PILIMage
from PIL import ImageTk
from tkinter import *

SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.readonly",  # Read Only Photos Library API
]

service = None
root = None

defaultConfig = config = {
    "mode": "all_media", #available modes: all_media, albums, search, favourites
    "albumNames": [],
    "searchString": "duck",
    "bgColor": "black",
    "photoDisplayTime": 5000
}

cached_albums = None
cached_media = dict()

def auto_filename(path, instance=0):
    """
    Recursively finds an available name for a new file and
    appends a number -> (#) to the end if that file already exists
    """
    if instance:
        extension_index = path.rfind(".")
        new_path = (
            path[:extension_index] + " (" + str(instance) + ")" + path[extension_index:]
        )
    else:
        new_path = path

    if not os.path.exists(new_path):
        return new_path
    else:
        return auto_filename(path, instance + 1)

def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.

def download_media_item(entry):
    try:
        url, path, description = entry
        r = requests.get(url)
        if r.status_code == 200:
            # path = auto_filename(path)
            if description:
                try:
                    img = Image.open(io.BytesIO(r.content))
                    exif_dict = piexif.load(img.info["exif"])
                    exif_dict["Exif"][
                        piexif.ExifIFD.UserComment
                    ] = piexif.helper.UserComment.dump(
                        description, encoding="unicode"
                    )

                    # This is a known bug with piexif (https://github.com/hMatoba/Piexif/issues/95)
                    if 41729 in exif_dict["Exif"]:
                        exif_dict["Exif"][41729] = bytes(
                            exif_dict["Exif"][41729]
                        )

                    exif_bytes = piexif.dump(exif_dict)
                    img.save(path, exif=exif_bytes)
                except ValueError:
                    # This value here is to catch a specific scenario with file extensions that have
                    # descriptions that are unsupported by Pillow so the program can't modify the EXIF data.
                    print(
                        " [INFO] media file unsupported, can't write description to EXIF data."
                    )
                    open(path, "wb").write(r.content)
            else:
                open(path, "wb").write(r.content)

            return (
                path
            )

    except Exception as e:
        print(" [ERROR] media item could not be downloaded because:", e)
        return False

def list_albums():

    global cached_albums

    if cached_albums != None:
        return cached_albums

    num = 0
    album_list = []
    request = service.albums().list(pageSize=50).execute()  # Max is 50
    if not request:
        return {}
    while True:
        if "albums" in request:
            album_list += request["albums"]
        if "nextPageToken" in request:
            next_page = request["nextPageToken"]
            request = (
                service.albums()
                .list(pageSize=50, pageToken=next_page)
                .execute()
            )
        else:
            break
        num += 1
    cached_albums = album_list
    return album_list

def getRandomImageFromFavourites():
    global cached_media
    print("getRandomImageFromFavourites")

    request_body = {
        "filters": {"featureFilter": {"includedFeatures": ["FAVORITES"]}, "mediaTypeFilter": {"mediaTypes": ["PHOTO"]}},
        "pageSize": 100,  # Max is 100
        "pageToken": "",
    }
    favorites_list = []

    if cached_media is not None and "favourites" in cached_media:
        favorites_list = cached_media["favourites"]
    else:
        request = service.mediaItems().search(body=request_body).execute()

        if not request:
            return

        if "mediaItems" in request:
            favorites_list += request["mediaItems"]
        cached_media["favourites"] = favorites_list

        while True:
            if "mediaItems" in request:
                favorites_list += request["mediaItems"]
            if "nextPageToken" in request:
                next_page = request["nextPageToken"]
                request_body["pageToken"] = next_page
                request = (
                    service.mediaItems()
                    .search(body=request_body)
                    .execute()
                )
            else:
                break
            cached_media["favourites"] = favorites_list

    randomPhotoIndex = random.randrange(0, len(favorites_list))

    download_media_item((favorites_list[randomPhotoIndex]["baseUrl"] + "=d", "./image.jpg", None))

def get_token():
    credentials_file = "./creds.json"
    token_path = "./token"
    credentials = None

    if os.path.exists(token_path):
        with open(token_path, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
        credentials = flow.run_local_server()

        with open(token_path, "wb") as token:
            pickle.dump(credentials, token)

    print(credentials)
    return build("photoslibrary", "v1", credentials=credentials, static_discovery=False)

def load_config():
    config = None
    if not (os.path.exists("config.yaml")):
        with io.open('config.yaml', 'w', encoding='utf8') as outfile:
            yaml.dump(defaultConfig, outfile, default_flow_style=False, allow_unicode=True)

    with open("config.yaml", 'r') as stream:
        config = yaml.safe_load(stream)

    return config

def getRandomImageFromAlbums(albumNames):
    global cached_media
    print("getRandomImageFromAlbum")

    if (len(albumNames) == 0):
        print("Did not provide any album names!")


    randomAlbumIndex = random.randrange(0, len(albumNames))
    albumName = albumNames[randomAlbumIndex]

    albums = list_albums()
    found = False
    foundAlbumID = ""

    for album in albums:
        if "title" not in album:
            album["title"] = "Unnamed Album"
        if album["title"] == albumName:
            found = True
            foundAlbumID = album["id"]
            break

    if not found:
        print("Did not found album {0}".format(str(albumName)))
        return

    # Make request
    album_items = []

    if cached_media is not None and foundAlbumID in cached_media:
        print("the album " + albumName +" is cached! woooohoooooooooooooooo")
        album_items = cached_media[foundAlbumID]
    else:
        print("the album " + albumName +" is not cached! boooo")
        request_body = {
            "albumId": foundAlbumID,
            "pageSize": 25,  # Max is 100
            "pageToken": "",
        }
        num = 0
        request = (
            service.mediaItems().search(body=request_body).execute()
        )  # 100 is max
        if not request:
            return
        while True:
            if "mediaItems" in request:
                album_items += request["mediaItems"]
            if "nextPageToken" in request:
                request_body["pageToken"] = request["nextPageToken"]
                request = service.mediaItems().search(body=request_body).execute()
            else:
                break
        cached_media[foundAlbumID] = album_items


    randomPhotoIndex = random.randrange(0, len(album_items))

    download_media_item((album_items[randomPhotoIndex]["baseUrl"] + "=d", "./image.jpg", None))

def getRandomImageFromAllLibrary():
    global cached_media
    print("getRandomImageFromAllLibrary")

    media_items_list = []

    if cached_media is not None and "AllMedia" in cached_media:
        media_items_list = cached_media["AllMedia"]
    else:
        request = service.mediaItems().list(pageSize=100).execute()  # Max is 50
        if not request:
            return {}
        while True:
            if "mediaItems" in request:
                media_items_list += request["mediaItems"]
            if "nextPageToken" in request:
                next_page = request["nextPageToken"]
                request = (
                    service.mediaItems()
                    .list(pageSize=100, pageToken=next_page)
                    .execute()
                )
            else:
                break
        cached_media["AllMedia"] = media_items_list

    randomPhotoIndex = random.randrange(0, len(media_items_list))

    download_media_item((media_items_list[randomPhotoIndex]["baseUrl"] + "=d", "./image.jpg", None))

def updateImage(imagePath):
    global root
    print("updateImage")
    # resize the image to fill the whole screen
    pilImage = PILIMage.open(imagePath)
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    imgWidth, imgHeight = pilImage.size
    # resize photo to full screen
    ratio = min(w / imgWidth, h / imgHeight)
    imgWidth = int(imgWidth * ratio)
    imgHeight = int(imgHeight * ratio)
    pilImage = pilImage.resize((imgWidth, imgHeight), PILIMage.ANTIALIAS)
    # image = ImageTk.PhotoImage(pilImage.resize((w,h)))
    image = ImageTk.PhotoImage(pilImage)
    # update the image
    canvas.itemconfig(imgbox, image=image)
    # need to keep a reference of the image, otherwise it will be garbage collected
    canvas.image = image
    # label['text'] = imagePath
    # label['image'] = image
    # label.photo = image
    # root.update_idletasks()
    # root.update()

def setupTkCanvas():
    print("setupTkCanvas")
    global root, canvas, imgbox
    root = Tk()
    root.attributes('-fullscreen', 1)
    root.bind('<Escape>', lambda _: root.destroy())
    canvas = Canvas(root, highlightthickness=0, bg=config["bgColor"])
    canvas.pack(fill=BOTH, expand=1)
    imgbox = canvas.create_image(root.winfo_screenwidth() / 2, 0, image=None, anchor='n')
    # label = Label(root, compound=TOP)
    # label.pack()
    # show the first image
    # change the image 5 seconds later
    # root.after(5000, updateRoot, 'Dog.jpg')

def PhotoLoop():

    while(True):
        time.sleep(config["photoDisplayTime"])
        DisplayNextPhoto()

def DisplayNextPhoto():
    print("DisplayNextPhoto")

    # available modes: all_media, albums, search, favourites
    if config["mode"] == "all_media":
        getRandomImageFromAllLibrary()
    elif config["mode"] == "albums":
        getRandomImageFromAlbums(config["albumNames"])
    elif config["mode"] == "search":
        print("Unsupported")
        return
    elif config["mode"] == "favourites":
        getRandomImageFromFavourites()
    else:
        print(("Unsupported mode:" + config["mode"]))
        return


    updateImage('image.jpg')
    root.after(config["photoDisplayTime"], DisplayNextPhoto)

if __name__ == '__main__':
    config = load_config()
    service = get_token()
    albums = list_albums()
    # print(albums.__str__())

    setupTkCanvas()
    DisplayNextPhoto()

    root.mainloop()


