## Multicolumn honors board requirments.

Make a new repository branch called multicolumn

The aim of this branch is to make a multicolumn version of the honors board. 

It should be possible to select 1,2,3 or 4 column versions of the board. USe a command line argument to specify the number of columns

There should be a background image defined for each version 

The data defining the positioning of the text on the board background should be defined in a JSON file using the parameters as shown in lines 18-28 of the current generate_boards.py file. In addition there should a text_x start co-ordiate for each column. The background image can be specified in the .JSON file - its root directory will remain as Board_background_images. Giove a warniong if a background image is not found.

The user interface should be updated to allow the number of columns for the generated board to be selected.

The board title should always be center aligned over the centre of the background image.

The output filenames will incorporate the column number.

The data should be split evenly across columns upto the maximum number of columns specified for the board.

We will work on the generate_boards.py file before turning attention to the UI

Start by creating an implementation plan for review remembering to make a phase 2 plan for the UI changes. Do not chnage any code until instructed.