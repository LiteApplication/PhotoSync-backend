# PhotoSync (WIP)
My own version of Google Photos.

This project's goal is to be able to self-host a photo backup service and access it from a web browser and Android.

The code is split into 3 parts
- The backend (this repo)
  - Powered by Flask
  - Custom API made by me
  - Handles a variety of file formats and generate thumbnails for them
  - Supports upload/download of multiple files at the same time
- The static web content [PhotoSync-web](https://github.com/LiteApplication/PhotoSync-web)
  - Written in HTML/CSS/JS
  - Uses the [Material Design Lite](https://getmdl.io/) library for the UI
- The Android application[PhotoSync-kotlin](https://github.com/LiteApplication/PhotoSync-kotlin)
  - Written in Kotlin
  - Optimised to display many images at the same time, from network, storage and cache.

This project is still in extremely early developpment and provided on an "as is" basis.

Feel free to explore the code.
