import dearpygui.dearpygui as dpg

dpg.create_context()

with dpg.window(label="AYAWrus Test"):
    dpg.add_text("If you see this, DPG works")
    dpg.add_button(label="Click me")

dpg.create_viewport(title='AYAWrus', width=600, height=400)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()