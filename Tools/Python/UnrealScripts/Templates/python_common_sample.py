"""
This file is for store some common python samples for someone who
too lazy to remember!!!
"""
raise Exception("You can not execute this file directly")


"""
Create dir if not exist
"""
import os
folder = "abc"
if not os.path.isdir(folder):
    os.mkdir(folder)


"""
try catch
"""
try:
  print("Hello")
except:
  print("Something went wrong")
else:
  print("Nothing went wrong")
finally:
  print("The 'try except' is finished")
  
  
"""
enum
"""
from enum import Enum
class Season(Enum):
    SPRING = 1
    SUMMER = 2
    AUTUMN = 3
    WINTER = 4
    
    
"""
Write File
"""
file_path = "D:/123.txt"
with open(file_path, 'w') as output_file:
    output_file.write('123')
    
    
"""
Ternary conditional operator 
"""
result = 'true' if True else 'false'
