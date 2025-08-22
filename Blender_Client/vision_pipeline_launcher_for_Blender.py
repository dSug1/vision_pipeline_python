bl_info = {
    "name": "Vision Pipeline Socket Launcher",
    "author": "Andre",
    "version": (1, 0),
    "blender": (3, 4, 1),
    "location": "View3D > Tool Shelf",
    "description": "Send inference command to external vision pipeline microservice",
    "category": "Development",
}

import bpy
import socket

HOST = '127.0.0.1'
PORT = 65432

class VISIONPIPELINE_OT_SendCommand(bpy.types.Operator):
    """Send inference command to vision pipeline microservice"""
    bl_idname = "visionpipeline.send_command"
    bl_label = "Run Vision Inference (Socket)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))
                s.sendall(b"run_inference")
                response = s.recv(1024).decode('utf-8')
                self.report({'INFO'}, f"Response: {response}")
        except Exception as e:
            self.report({'ERROR'}, f"Socket error: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

class VISIONPIPELINE_PT_Panel(bpy.types.Panel):
    """Vision Pipeline Panel"""
    bl_label = "Vision Pipeline"
    bl_idname = "VISIONPIPELINE_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Vision'

    def draw(self, context):
        layout = self.layout
        layout.operator("visionpipeline.send_command")

def register():
    bpy.utils.register_class(VISIONPIPELINE_OT_SendCommand)
    bpy.utils.register_class(VISIONPIPELINE_PT_Panel)

def unregister():
    bpy.utils.unregister_class(VISIONPIPELINE_OT_SendCommand)
    bpy.utils.unregister_class(VISIONPIPELINE_PT_Panel)

if __name__ == "__main__":
    register()
