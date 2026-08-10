BATTERY MANAGEMENT: BQ25892
    CHG_PSEL: soll bei BQ25892 HIGH für USB host source. Ist das nicht der Fall bei uns?
    TS: Was wenn 103AT NTC nicht gegeben ist oder ein anderer?
    CHG_PG: Da steht PIN 3 bei BQ25892 und nicht bei BQ25890!
    SDA und SCL: 10kOhm resistor where to place? What and where is the logic rail?
    ILIM: How did you calculate R_ILIM and what is K_ILIM?
    BATFET: What is it? What is ship mode (QON)?
    Make an LED charging indicator: I already added one but check it yourself again.
    Second-source-option field: Shouldnt this be for the 892 aswell. Check again if you have some pin mismatches between 892 and 890.
    Layout Guidelines: Different grounds!
    Remind me of Layout Guidelines when it comes to it.
Battery Connection: I think a jst connector might not be the best connector for this purpose. Its pretty high and takes up vertical space. Maybe directly soldering the battery to pads on the pcb could be viable. Or a diffrent connector.
USB: Upgrade to USB3 if possible, for fast file transfer! Explain what to change and find a datasheet/ressource for connecting info.
Fuel Guage: MAX17048
    CELL: PIN not connected.
    QSTRT: What about the hardware quick-start. DO we need it?
    
