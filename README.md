# MoC Utils

## TODO

- [x] adding db dump to the cli
- [x] rewriting db dump to dump localisation as seperate file
- [ ] adding tests
- [ ] use EncryptDebugString to decrypt error messages of the lua handler


## Installation

```shell
pip install -U git+https://github.com/Miners-of-Convallaria/utils.git
```

or if cloned within the directory

```shell
pip install -e .
```


## CLI

```shell
Usage: python -m moc_utils COMMAND SUBCOMMAND --parameter1 value1 --parameter2 value2 ...

Commands:
  download
  news
  database


download:
  A downloader for various items available via the cdn of the game.

  Subcommands
  ---
  launcher
    Downloads the launcher for the game.
  game
    Downloads the game files for running the game.
  assets
    Downloads the assets for the game.

  Parameters
  ---
  dst: str
      Path to save the files to.
  cdn: str
      cdn to use (us-prod, tw-prod, jp-prod, cn-prod)
  channel: Optional[str]
      channel to use.
  loc: Optional[str]
      localisation to use (None (default), en, ja, ko, zh-cn, zh-tw).


news:
  A news fetcher for the game.

  Subcommands
  ---
  link:
    Returns the link to the news.
  download_details
    Downloads the news details.


  Parameters
  ---
  cdn: str
      cdn to use (us-prod, tw-prod, jp-prod, cn-prod)
  channel: Optional[str]
      channel to use.
  lang: Optional[str]
      language to use (None (default), en_US, zh_TW, ja_JP, zh_CN).
  dst: Optional[str] - for download_details
      path to save files to

database
  A database dumper for the game.

  Subcommands
  ---
  from_game:
    Dumps the database using the game instance.
  from_server:
    Dumps the database using the assets from the server.
  
  Parameters
  ---
  dst: str
      Path to save the files to.
  loc: Optional[str]
      localisation to use (none (default), en, ja, ko, zh-cn, zh-tw).
  area: Optional[str]
      area to use (none (default), us, tw, kr, jp, cn).
  game_dir: Optional[str] - for from_game
      path to the game installation
  cdn: Optional[str] - for from_server
      cdn to use (us-prod, tw-prod, jp-prod, cn-prod)
  channel: Optional[str] - for from_server
      channel to use.
```

### examples

**Downloading/Updating all assets of the global client with english localisation**
``python -m moc_utils download assets --dst D:\\SoC\\assets --cdn us-prod --lang en``

**Get all currently shown news of the tw server as json**
``python -m moc_utils news download_details --dst D:\\SoC\\news --cdn tw-prod``
