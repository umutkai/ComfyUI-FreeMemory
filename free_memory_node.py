import torch
import gc
import psutil
import os
import ctypes
import comfy.model_management as mm
import subprocess # Import subprocess

class FreeMemoryBase:
    # --- Keep the FreeMemoryBase class exactly as defined in the previous response ---
    # (Including the modified free_system_ram with subprocess)
    def free_memory(self, aggressive=False):
        print("Attempting to free GPU VRAM and system RAM...")
        self.free_gpu_vram(aggressive)
        self.free_system_ram(aggressive)

    def free_gpu_vram(self, aggressive):
        if torch.cuda.is_available():
            initial_vram = mm.get_total_memory_vram()
            allocated_vram = torch.cuda.memory_allocated() / (1024**3) # GB
            reserved_vram = torch.cuda.memory_reserved() / (1024**3) # GB
            print(f"GPU VRAM Before: Allocated={allocated_vram:.2f}GB, Reserved={reserved_vram:.2f}GB, Total={initial_vram/(1024**3):.2f}GB")

            torch.cuda.empty_cache()
            print("torch.cuda.empty_cache() called.")

            gc.collect()
            if aggressive:
                print("Aggressive VRAM Free: Unloading all models...")
                mm.unload_all_models()
            else:
                pass

            torch.cuda.empty_cache()

            gc.collect()
            final_allocated_vram = torch.cuda.memory_allocated() / (1024**3)
            final_reserved_vram = torch.cuda.memory_reserved() / (1024**3)
            freed_allocated = (allocated_vram * (1024**3) - final_allocated_vram * (1024**3)) # Bytes
            print(f"GPU VRAM After: Allocated={final_allocated_vram:.2f}GB, Reserved={final_reserved_vram:.2f}GB")
            print(f"GPU VRAM Freed (Allocated): {freed_allocated / (1024**3):.3f} GB")
        else:
            print("CUDA is not available. No GPU VRAM to free.")

    def free_system_ram(self, aggressive):
        initial_memory_info = psutil.virtual_memory()
        initial_percent = initial_memory_info.percent
        initial_available_gb = initial_memory_info.available / (1024**3)
        print(f"System RAM Before: Usage={initial_percent:.1f}%, Available={initial_available_gb:.2f}GB")

        collected = gc.collect()
        print(f"Garbage collector: collected {collected} objects.")

        if aggressive:
            print("Attempting Aggressive System RAM clearing...")
            if os.name == 'posix':
                try:
                    print("Running sync command...")
                    sync_process = subprocess.run(['sync'], check=True, capture_output=True, text=True, timeout=30)
                    print("Sync completed successfully.")
                except FileNotFoundError: print("Error: 'sync' command not found.")
                except subprocess.CalledProcessError as e: print(f"Error running sync: Exit code {e.returncode}\nStderr: {e.stderr}\nStdout: {e.stdout}")
                except subprocess.TimeoutExpired: print("Error: 'sync' command timed out.")
                except Exception as e: print(f"An unexpected error occurred during sync: {str(e)}")

                try:
                    print("Attempting to drop caches via tee (writing '3' to /proc/sys/vm/drop_caches)...")
                    drop_process = subprocess.run(
                        ['tee', '/proc/sys/vm/drop_caches'], input='3', text=True, check=True, capture_output=True, timeout=10
                    )
                    print("Command to drop caches executed via tee.")
                    if drop_process.stderr: print(f"Drop caches command (tee) produced stderr: {drop_process.stderr.strip()}")
                except FileNotFoundError: print("Error: 'tee' command not found.")
                except subprocess.CalledProcessError as e: print(f"Error executing tee to drop caches: Exit code {e.returncode}\nStderr: {e.stderr.strip()}\nStdout: {e.stdout.strip()}\n(Check permissions?)")
                except subprocess.TimeoutExpired: print("Error: 'tee' command timed out.")
                except Exception as e: print(f"An unexpected error occurred during drop caches via tee: {str(e)}")

            elif os.name == 'nt':
                try:
                    print("Attempting to clear working set on Windows...")
                    result = ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
                    if result: print("Windows EmptyWorkingSet call succeeded.")
                    else: print("Windows EmptyWorkingSet call returned false.")
                except AttributeError: print("Failed to call EmptyWorkingSet: Function not found.")
                except Exception as e: print(f"Failed to clear working set on Windows: {str(e)}")
            else: print(f"Aggressive system RAM clearing not implemented for OS: {os.name}")

        final_memory_info = psutil.virtual_memory()
        final_percent = final_memory_info.percent
        final_available_gb = final_memory_info.available / (1024**3)
        memory_freed_percent_points = initial_percent - final_percent
        print(f"System RAM After: Usage={final_percent:.1f}%, Available={final_available_gb:.2f}GB")
        print(f"System RAM Usage Change: {memory_freed_percent_points:.1f} percentage points")


class FreeMemoryImage(FreeMemoryBase):
    @classmethod
    def INPUT_TYPES(s): return {"required": { "image": ("IMAGE",), "aggressive": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "free_memory_passthrough"
    CATEGORY = "Memory Utils"
    def free_memory_passthrough(self, image, aggressive): self.free_memory(aggressive=aggressive); return (image,)

class FreeMemoryLatent(FreeMemoryBase):
    @classmethod
    def INPUT_TYPES(s): return {"required": { "latent": ("LATENT",), "aggressive": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("LATENT",)
    FUNCTION = "free_memory_passthrough"
    CATEGORY = "Memory Utils"
    def free_memory_passthrough(self, latent, aggressive): self.free_memory(aggressive=aggressive); return (latent,)

class FreeMemoryModel(FreeMemoryBase):
    @classmethod
    def INPUT_TYPES(s): return {"required": { "model": ("MODEL",), "aggressive": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("MODEL",)
    FUNCTION = "free_memory_passthrough"
    CATEGORY = "Memory Utils"
    def free_memory_passthrough(self, model, aggressive): self.free_memory(aggressive=aggressive); return (model,)

class FreeMemoryCLIP(FreeMemoryBase):
    @classmethod
    def INPUT_TYPES(s): return {"required": { "clip": ("CLIP",), "aggressive": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("CLIP",)
    FUNCTION = "free_memory_passthrough"
    CATEGORY = "Memory Utils"
    def free_memory_passthrough(self, clip, aggressive): self.free_memory(aggressive=aggressive); return (clip,)

# --- Added FreeMemoryString back ---
class FreeMemoryString(FreeMemoryBase):
    @classmethod
    def INPUT_TYPES(s):
        # STRING inputs in ComfyUI can be multi-line text boxes by default.
        # Using "forceInput: True" makes it an input connector instead of a widget.
        # You might want either behavior depending on how you trigger it.
        # Option 1: Text widget (default if no options given or using multiline)
        # return {"required": { "string": ("STRING", {"multiline": False}), "aggressive": ("BOOLEAN", {"default": False}) }}
        # Option 2: Input connector (useful if triggered by another node's string output)
        return {"required": {
                    "string": ("STRING", {"forceInput": True}), # Makes it an input connector
                    "aggressive": ("BOOLEAN", {"default": False})
               }}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "free_memory_passthrough" # Use consistent passthrough name
    CATEGORY = "Memory Utils"

    def free_memory_passthrough(self, string, aggressive):
        # The input 'string' acts purely as a trigger here.
        print(f"FreeMemoryString triggered by string: '{str(string)[:50]}...'") # Log trigger
        self.free_memory(aggressive=aggressive)
        return (string,) # Pass the triggering string through
# --- End FreeMemoryString ---

NODE_CLASS_MAPPINGS = {
    "FreeMemoryImage": FreeMemoryImage,
    "FreeMemoryLatent": FreeMemoryLatent,
    "FreeMemoryModel": FreeMemoryModel,
    "FreeMemoryCLIP": FreeMemoryCLIP,
    "FreeMemoryString": FreeMemoryString, # Added back
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FreeMemoryImage": "Free Memory (Image Trigger)",
    "FreeMemoryLatent": "Free Memory (Latent Trigger)",
    "FreeMemoryModel": "Free Memory (Model Trigger)",
    "FreeMemoryCLIP": "Free Memory (CLIP Trigger)",
    "FreeMemoryString": "Free Memory (String Trigger)", # Added back
}

print("Loaded FreeMemory Nodes (with subprocess drop_caches)")
