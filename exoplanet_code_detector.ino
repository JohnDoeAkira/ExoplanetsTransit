//#include <Wire.h>                             
#include <SD.h>                               // SD card library 
#include <SPI.h>

int LDR = A0;

int chipSelect = 3; 
File datalogger; 

void setup() 
{
Serial.begin(250000);
pinMode(LDR, INPUT);
SD.begin(3); 

 datalogger = SD.open("data.txt", FILE_WRITE);  
 datalogger.print("\n");
 datalogger.println("--------------- New reading ---------------");
 datalogger.println("\n");
 datalogger.print("\n");
 datalogger.close();

}

void loop() {

int LDRValue = analogRead(LDR);
  
datalogger = SD.open("data.txt", FILE_WRITE);               // Crate 'data.txt' file and open it  
  
            
            if (datalogger) {

            float time = millis();
            int LDRValue = analogRead(LDR);
              
            datalogger.print("I= ");                                  // Write 'U = ' in the data.txt file 
            datalogger.print("\t");                                    // Tabulator in the data.txt file
            datalogger.print(LDRValue, 1);                               // Write sensor 1 reading in the data.txt file
            datalogger.print("\t");                                    // Tabulator in the data.txt file
            datalogger.print("t= ");                                  // Write 't =' in the data.txt file 
            datalogger.print("\t");                                    // Tabulator in the data.txt file
            datalogger.print(time, 1);                                // Write time in the data.txt file
            datalogger.println("\n");                                  // New line in the data.txt file
            datalogger.close(); }



Serial.println(LDRValue);
delay(1);



}
