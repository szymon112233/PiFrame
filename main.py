# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
import io
import pickle
import random
import time
import tkinter
import win32api

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
second_window = None
date_label = None
date_text = None
current_image_data = None
pause = False
nextPhotoJob = None
inactivityCheckJob = None

defaultConfig = config = {
    "mode": "all_media", #available modes: all_media, albums, search, favourites
    "albumNames": [],
    "searchString": "duck",
    "bgColor": "black",
    "infoTextFont": "Helvetica",
    "infoTextFontSize": 14,
    "infoTextColor": "white",
    "photoDisplayTime": 5000,
    "showControlsWindow": True,
    "inactivityThresholdTime": 60000
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

            return (path)

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
    global cached_media, current_image_data
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
    current_image_data = favorites_list[randomPhotoIndex]

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
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            credentials = flow.run_local_server()

        with open(token_path, "wb") as token:
            pickle.dump(credentials, token)

    print(credentials)
    return build("photoslibrary", "v1", credentials=credentials, static_discovery=False)

def load_config():
    config = None
    if not (os.path.exists("config/config.yaml")):
        with io.open('config/config.yaml', 'w', encoding='utf8') as outfile:
            yaml.dump(defaultConfig, outfile, default_flow_style=False, allow_unicode=True)

    with open("config/config.yaml", 'r') as stream:
        config = yaml.safe_load(stream)

    return config

def getRandomImageFromAlbums(albumNames):
    global cached_media, current_image_data
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
    current_image_data = album_items[randomPhotoIndex]

    download_media_item((album_items[randomPhotoIndex]["baseUrl"] + "=d", "./image.jpg", None))

def getRandomImageFromAllLibrary():
    global cached_media, current_image_data
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
    current_image_data = media_items_list[randomPhotoIndex]

    download_media_item((media_items_list[randomPhotoIndex]["baseUrl"] + "=d", "./image.jpg", None))


def Pause():
    global root, pause, nextPhotoJob, inactivityCheckJob
    print("Pause")
    pause = True
    second_window.withdraw()
    root.after_cancel(nextPhotoJob)
    inactivityCheckJob = root.after(1000, CheckIdle)

def UnPause():
    global pause
    print("UnPause")
    pause = False
    second_window.deiconify()
    DisplayNextPhoto()

def LeftButtonClicked():
    print("LeftButtonClicked")

def RightButtonClicked():
    print("RightButtonClicked")

def PictureButtonClicked():
    print("PictureButtonClicked")
    Pause()


def ScreenClicked(event):
    global root
    x = event.x
    y = event.y
    print(f"Mouse clicked at coordinates (x={x}, y={y})")

    sideButtonsRatio = 0.1
    screenWidth = root.winfo_screenwidth()

    if x < sideButtonsRatio * screenWidth:
        LeftButtonClicked()
    elif x < (1 - sideButtonsRatio) * screenWidth:
        PictureButtonClicked()
    else:
        RightButtonClicked()

def get_idle_time() -> float:
    return (win32api.GetTickCount() - win32api.GetLastInputInfo()) / 1000

def CheckIdle():
    global root, inactivityCheckJob
    print("CheckIdle")
    if get_idle_time() > config["inactivityThresholdTime"]:
        UnPause()
        root.after_cancel(inactivityCheckJob)
    else:
        inactivityCheckJob = root.after(1000, CheckIdle)

def updateImage(imagePath):
    global root, date_label, current_image_data, date_text
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

    text = current_image_data["mediaMetadata"]["creationTime"]
    if "contributorInfo" in current_image_data:
        text += (" by " + current_image_data["contributorInfo"]["displayName"])

    canvas.itemconfig(date_text, text=text)

    # label['text'] = imagePath
    # label['image'] = image
    # label.photo = image
    # root.update_idletasks()
    # root.update()

def setupTkCanvas():
    print("setupTkCanvas")
    global root, second_window, canvas, imgbox, date_label, date_text, inactivityCheckJob
    root = Tk()
    # root.attributes('-fullscreen', 1)
    root.bind('<Escape>', lambda _: root.destroy())
    root.title("PiFrame controls")
    # inactivityCheckJob = root.after(1000, CheckIdle)

    if config["showControlsWindow"]:
        root.geometry("200x200")
        # root.iconify()
    else:
        root.overrideredirect(True)
        root.geometry("0x0")

    button = Button(root, text='Show', command=UnPause)
    button.pack()

    second_window = Toplevel()
    second_window.attributes('-fullscreen', 1)
    second_window.bind('<1>', ScreenClicked)
    second_window.lift(root)
    canvas = Canvas(second_window, highlightthickness=0, bg=config["bgColor"])
    canvas.pack(fill=BOTH, expand=1)
    imgbox = canvas.create_image(root.winfo_screenwidth() / 2, 0, image=None, anchor='n')
    date_text = canvas.create_text((0, 0), text="test", anchor=NW, fill=config["infoTextColor"], font=(config["infoTextFont"], config["infoTextFontSize"]))

    # LeftButton = Button(canvas, text='LEFT', command=LeftButtonClicked)
    # LeftButton.place(anchor=NW, x=0, y=0, relheight=1.0, relwidth=0.1)
    # LeftButton.lower()
    # PictureButton = Button(canvas, text='PICTURE', command=PictureButtonClicked)
    # PictureButton.place(anchor=N, x=root.winfo_screenwidth()/2, y=0, relheight=1.0, relwidth=0.8)
    # RightButton = Button(canvas, text='RIGHT', command=RightButtonClicked)
    # RightButton.place(anchor=NE, x=root.winfo_screenwidth(), y=0, relheight=1.0, relwidth=0.1)
    # date_label = Label(root, text="233312312312", font=("Helvetica", 14), bg="transparent", fg="white")
    # date_label.place(x=20, y=10)
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
    global nextPhotoJob
    print("DisplayNextPhoto")
    if pause:
        return

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
    nextPhotoJob = root.after(config["photoDisplayTime"], DisplayNextPhoto)

if __name__ == '__main__':
    config = load_config()
    service = get_token()
    albums = list_albums()
    # print(albums.__str__())

    setupTkCanvas()
    DisplayNextPhoto()

    root.mainloop()


