Frontlight_sch see below
FL_INT#: As far as I see it, this is unconnected? Will it connect somewhere eventually?
General: It seems like the suppliers dont want to talk to me when I quote small display quantities or idk, but they dont respond. I guess that I have to check it somehow else when I get the display to my test bench. But keep this for now.
IN: "Input voltage connection. Connect a 2.3-V to 5.5-V supply to IN and bypass to GND with a 2.2-µF or greater ceramic capacitor" why do we have 4,7uF + 100nF?
COUT: Cout is 2.2uF here; I havent found any guidlines on how to choose this capacitor but in 10.2 Layout Example in the image it says:"COUT (603 1uF)" How did you get to 2.2uF?
J24: Why are half of the pins not used? I cant find anything about how the leds are connected.

IO_expansion see below
Why is touch input disabled? The display I bought has a touch panel and the datasheet of the controller thats used is in parts/Display GT911...
Specifically look at the bottom left in 9. Sample Schematic.
Pin 1 is GND, 4 is SCL, 5 is SDA etc.
