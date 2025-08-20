- 	The vision pipeline is packaged as a microservice that can be called via socket.

	How to Run It?

	-> The MediaPipe tasks require the mediapipe PyPI package. You can install and import these dependencies with the following:


		$ python -m pip install mediapipe


	(google search: "how to install mediapipe for python)


	-> Open a terminal from the vision_pipeline_python folder and run the below command to start the server:

		bash
		python server.py


-	Then, to use it inside Blender :
	-> Launch Blender, install and enable the add-on vision_pipeline_launcher.

	-> Click “Run Vision Inference (Socket)” in the UI panel.


- If you later want to expose server.py as a CLI tool or daemon, this structure will make that transition seamless.
	Want help wrapping server.py in a CLI or turning it into a background service? I’ve got ideas.


-	Let me know if you want to:

	Send JSON payloads from Blender (e.g. config, resolution)

	Return detection results to Blender

	Auto-launch this server from the Blender add-on





- If you want to integrate the pipeline directly into Blender’s viewport (e.g. overlaying results on a texture or UI panel), we can refactor Main.py to expose functions instead of running a loop, and call those from Blender using bpy.app.timers or modal operators.
Would you like to modularize Main.py next so it can be reused both externally and inside Blender?