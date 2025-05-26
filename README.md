# LG TV Serial

Custom integration for Home Assistant to control LG TVs that support the serial control protocol

The protocol is [documented by LG here](https://www.lg.com/ca_en/support/product-support/troubleshoot/help-library/cs-CT20098005-20153058982994/). Kudos for LG for making the protocol specification available.

This is a quickly whipped up integration but seems to work fine for me for a while now (mostly to just turn on/off the TV).

I am unsure for what range of TV models this applies, I have an older model from 2011 which has a DB9 serial connector for this protocol. Check the owners manual of your TV (downloadable from LG website) to see if it supports this protocol.

## Gotchas

It takes a while for the TV to change actual state when turning on/off. This is indicated (a bit hacky) by using the state "Buffering". When state is ON it is safe to send other commands.

Most entities can not be used when the TV is Off, so these entities become unavailable to indicate that.

## Features

Connect through serial or any [URL handler supported by PySerial](https://pyserial.readthedocs.io/en/latest/url_handlers.html) this makes it possible to connect through networked tcp-2-serial solutions so your TV does not have to be connected directly to your Home Assistant machine.

### Mediaplayer

Mediaplayer entity that supports:

* On/off
* Volume
* Mute
* Input selection

### Remote control

Remote control entity that supports the following commands. Check the `commands` attribute of the entity for the full up-to-date list of supported commands. The list below might get out of date.

>ch_plus, ch_minus, volume_plus, volume_minus, arrow_right, arrow_left, power, mute, input, sleep, tv_radio, number_0, number_1, number_2, number_3, number_4, number_5, number_6, number_7, number_8, number_9, q_view_flashback, fav, teletext, teletext_options, return_back, av_mode, caption_subtitle, arrow_up, arrow_down, my_apps, menu_settings, ok_enter, q_menu, list_minus, picture, sound, list, exit, pip, blue, yellow, green, red, aspect_ratio, audio_description, live_menu, user_guide, smart_home, simplink, forward, rewind, info, program_guide, play, stop_filelist, recent, freeze_slowplay_pause, soccer, rec, three_d, autoconfig, app, tv_pc

### Control lock switch

Switch that enables/disables IR remote control according to the manual

### Energy Saving select

Select that allows to select Energy Saving modes. Note that the entity is disabled by default.

### Action for sending raw commands

If there is a need to send commands that are not supported one can use the "lg_tv_serial.send_raw" action. Check the LG documentation for the command formats.

See example below, check out the developer tools in Home Assistant for more details.

```yaml
action: lg_tv_serial.send_raw
target:
  entity_id:
    - media_player.lg_tv
data:
  command1: k
  command2: e
  data0: "1"
```

## Download

### Home Assistant Community Store (HACS)

*Recommended as you get notifications of updates*

HACS is a 3rd party downloader for Home Assistant to easily install and update custom integrations made by the community. More information and installation instructions can be found on their site https://hacs.xyz/

* Add this repository https://github.com/mvdwetering/lg_tv_serial to HACS as a "custom repository" with category "integration". This option can be found in the ⋮ menu
* Install the integration from within HACS
* Restart Home Assistant

### Manual

* Download the release zip file
* Extract the Zip file in the `custom_components` directory
* Restart Home Assistant

## Configure

Configure the integration as usual.

* Go to Settings > Devices and Services and press Add Integration.
* Search for "LG TV Serial"
* Provide the serial port to which the TV is connected
  * For real serial ports usually something like "/dev/ttyUSB0"
  * When you use a tcp-to-serial converter you can probably use "socket://1.2.3.4:5678" where the IP and Port have to be changed for your situation
