import cv2
from cv2 import data

face_cascade = cv2.CascadeClassifier(data.haarcascades + "haarcascade_frontalface_default.xml")

image_path = input("Enter image path: ")
image = cv2.imread(image_path)

if image is None:
    print("Image not found")
    exit()

# grayscale for better detection
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

# lets find faces
# cascade detector runs on th eimage and returns a rectangle coordinate x,y,w,h
# scalefactor repatedly scales image by value to detet faces in differnet sizes
# minneighbour decides how many rectabgles should be overlapped to trigger face detection
# minsize ignores detected objects smaller tha 30x30 pixels
faces = face_cascade.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(30,30))

#looping over detected face coords
for (x,y,w,h) in faces:
    # extacts the subarray containing detected face
    face = image[y:y+h,x:x+w]
    # numpy doesnt use a copy but views into image
    # lets apply guassian blur
    blurred_face = cv2.GaussianBlur(face,(99,99),30)
    # (99, 99) is the kernel size. stronger blr
    # 30 is sigmaX (standard deviation in the X direction). used to make rexziabke with face sizes
    # we can write blurred_face in original image
    image[y:y+h, x:x+w] = blurred_face
    
output_path = "blurred_" + image_path.split("/")[-1]
cv2.imwrite(output_path,image)
# show image...comment out if not needed
cv2.imshow("Blurred Image", image)
cv2.waitKey(0)
cv2.destroyAllWindows()

