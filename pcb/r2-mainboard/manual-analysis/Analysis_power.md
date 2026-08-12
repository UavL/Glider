TPS62A02DRLR: 
    EN PIN: Do I understand correctly, that This chip provides 1.2 V and the EN Pin gets pulled to HIGH via MCU_EN_FPGA_CORE from the mcu and if the mcu signal is low then en gets pulled to gnd over the resistor?
    Write down all Layout Guidelines not just for this chip in the pcb design notes.
    R29: Typical Application says 200kOhm
    R32: VIN is diffreent for the VIN PIN and the PG PIN. Is this okay?
TPS63802DLAR:
    AGND and GND. Is it okay to connect together?
    R3: Why is it 470kOhm and not 100k?
TPS22965DSGR:
    Explain why this is used in tandem wit the TPS61022RWUR.
    Doesnt VSYS have to be defined via input flag?
    VBIAS==VSYS is ok? What is the VSYS voltage?
    C_IN: In 10.1.2 Input Capacitor 1 mueF is said to be sufficient. Why do we use 22mueF + 100nF? C22 + C24. In 10.1.3 a ratio of 10 to 1 for the Output C is mentioned.
TPS61022RWUR:
    C1: No C1 because we have the capacitor from before?
    C2: is 3x22uF in the typical application. So why do we have  only two?
    
PART Numbers: To my understanding a bom csv has to be sent with all part numbers for the parts used. Do I have to put them in the descriptions of the parts or will you do this at the end?
