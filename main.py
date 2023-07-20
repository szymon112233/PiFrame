# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import os
import io
import pickle
import piexif
import piexif.helper
import requests
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
        if not os.path.isfile(path):
            r = requests.get(url)
            if r.status_code == 200:
                path = auto_filename(path)
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

        else:
            return False
    except Exception as e:
        print(" [ERROR] media item could not be downloaded because:", e)
        return False

def list_albums():
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
    return album_list

def get_favourites():
    request_body = {
        "filters": {"featureFilter": {"includedFeatures": ["FAVORITES"]}},
        "pageSize": 100,  # Max is 100
        "pageToken": "",
    }
    favorites_list = []

    request = service.mediaItems().search(body=request_body).execute()

    if "mediaItems" in request:
        favorites_list += request["mediaItems"]

    return favorites_list

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


def updateImage(imagePath):
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


if __name__ == '__main__':
    print_hi('PyCharm')
    service = get_token()
    # albums = list_albums()
    # print(albums.__str__())

    # download_media_item(("", "", None))

    fav = get_favourites()
    print(fav.__str__())
    download_media_item((fav[0]["baseUrl"] + "=d", "./image.jpg", None))

    root = Tk()
    root.attributes('-fullscreen', 1)
    root.bind('<Escape>', lambda _: root.destroy())

    canvas = Canvas(root, highlightthickness=0, bg="black")
    canvas.pack(fill=BOTH, expand=1)
    imgbox = canvas.create_image(root.winfo_screenwidth()/2, 0, image=None, anchor='n')
    # label = Label(root, compound=TOP)
    # label.pack()

    # show the first image
    updateImage('image.jpg')
    # change the image 5 seconds later
    # root.after(5000, updateRoot, 'Dog.jpg')

    root.mainloop()

