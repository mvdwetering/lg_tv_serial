# LG TV Serial

Custom integration for Home Assistant to control LG TVs that support the serial control protocol

The protocol is [documented by LG here](https://www.lg.com/ca_en/support/product-support/troubleshoot/help-library/cs-CT20098005-20153058982994/). Thank you LG for not hiding the protocol specs like some other manufacturers do.

The integration works for me. Only manual tested a bit, but good enough for now.

Note that it takes a while for the TV to change state after turning on/off. This is indicated (a bit hacky) by using the state "Buffering". When state is ON it is safe to send commands.
