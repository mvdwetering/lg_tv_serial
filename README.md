# LG TV Serial

Custom integration for Home Assistant to control LG TVs that support the serial control protocol

The protocol is [documented by LG here](https://www.lg.com/ca_en/support/product-support/troubleshoot/help-library/cs-CT20098005-20153058982994/). Kudos for LG for making the protocol specification available.

This is a quick-and-dirty integration and is only manual tested a bit. But seems to work fine for me for a while now. 

I am unsure for what range of TV models this applies, I have an older model from 2011 which has a DB9 serial connector for this protocol. Check the owners manual of your TV (downloadable from LG website) to see if it supports this protocol.

# Gotchas

It takes a while for the TV to change actual state when turning on/off. This is indicated (a bit hacky) by using the state "Buffering". When state is ON it is safe to send other commands.

Remote entity and control lock can not be used when the TV is Off, so these entities become unavailable to indicate that.

## Features

Connect through serial or any [URL handler supported by PySerial](https://pyserial.readthedocs.io/en/latest/url_handlers.html) this makes it possible to connect through networked tcp-2-serial solutions so your TV does not have to be connected directly to your Home Assistant machine.

Mediaplayer with following features
* On/off
* Volume
* Mute
* Input selection

Remote control enity. Check the `commands` attribute of the entity for the full up-to-date list of supported commands. The list below might get out of date.

>ch_plus, ch_minus, volume_plus, volume_minus, arrow_right, arrow_left, power, mute, input, sleep, tv_radio, number_0, number_1, number_2, number_3, number_4, number_5, number_6, number_7, number_8, number_9, q_view_flashback, fav, teletext, teletext_options, return_back, av_mode, caption_subtitle, arrow_up, arrow_down, my_apps, menu_settings, ok_enter, q_menu, list_minus, picture, sound, list, exit, pip, blue, yellow, green, red, aspect_ratio, audio_description, live_menu, user_guide, smart_home, simplink, forward, rewind, info, program_guide, play, stop_filelist, recent, freeze_slowplay_pause, soccer, rec, three_d, autoconfig, app, tv_pc

Control lock switch
* Enables/disables IR remote control
