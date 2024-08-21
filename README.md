# MoC Utils

## TODO

- [] adding db dump to the cli
- [] rewriting db dump to dump localisation as seperate file
- [] adding tests
- [] use EncryptDebugString to decrypt error messages of the lua handler


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
Usage: python -m moc_utils [OPTIONS] COMMAND [ARGS]...

Options:
  --dst TEXT      Path to save the files to.  [required]
  --cdn TEXT      cdn to use (us-prod, tw-prod, jp-prod, cn-prod)  [required]
  --channel TEXT  channel to use.
  --lang TEXT     language to use
  --help          Show this message and exit.

Commands:
  download-assets    Download the assets.
  download-game      Download the game files (not assets).
  download-launcher  Download the launcher installer.
  news-details       stores all current news with their details/content
  news-link          prints the news link for the given server
```

### examples

**Downloading/Updating all assets of the global client with english localisation**
``python -m moc_utils --dst D:\\SoC\\assets --cdn us-prod --lang en download-assets``

**Get all currently shown news of the tw server as json**
``python -m moc_utils --dst D:\\SoC\\news --cdn tw-prod news-details``
