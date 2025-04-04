# --- Start of File: e.g., ComfyUI/custom_nodes/free_memory_nodes.py ---

import torch
import gc
import psutil
import os
import ctypes
import comfy.model_management as mm
import subprocess # For system commands

# Helper function to format bytes into GB
def bytes_to_gb(b):
    return b / (1024**3)

class FreeMemoryBase:
    """
    Base class containing the logic to free GPU and System RAM.
    Passthrough nodes inherit from this.
    """
    def free_memory(self, aggressive=False):
        """Calls both GPU and System RAM freeing functions."""
        print("----------------------------------------")
        print("⚡ FreeMemory Node: Attempting to free memory...")
        self.free_gpu_vram(aggressive)
        self.free_system_ram(aggressive)
        print("⚡ FreeMemory Node: Memory freeing attempt finished.")
        print("----------------------------------------")

    def free_gpu_vram(self, aggressive):
        """Frees GPU VRAM using torch.cuda.empty_cache() and optionally unloads models."""
        print("[Memory Utils] Attempting to Free GPU VRAM...")
        if not torch.cuda.is_available():
            print("[Memory Utils] CUDA not available. Skipping GPU VRAM freeing.")
            return

        # Initial VRAM stats
        try:
            initial_allocated_gb = bytes_to_gb(torch.cuda.memory_allocated())
            initial_reserved_gb = bytes_to_gb(torch.cuda.memory_reserved())
            print(f"[Memory Utils] GPU VRAM Before: Allocated={initial_allocated_gb:.2f}GB, Reserved={initial_reserved_gb:.2f}GB")
        except Exception as e:
            print(f"[Memory Utils] Warning: Could not get initial VRAM stats - {e}")
            initial_allocated_gb = 0 # Assume 0 if error

        # Basic cleanup
        gc.collect()
        torch.cuda.empty_cache()
        print("[Memory Utils] Called torch.cuda.empty_cache()")

        # Aggressive cleanup (unload models)
        if aggressive:
            print("[Memory Utils] Aggressive Mode: Unloading models...")
            try:
                mm.unload_all_models()
                gc.collect()
                torch.cuda.empty_cache()
                print("[Memory Utils] Models unloaded and cache emptied again.")
            except Exception as e:
                print(f"[Memory Utils] Error during aggressive model unload: {e}")
        else:
            print("[Memory Utils] Non-Aggressive Mode: Models kept loaded.")


        # Final VRAM stats
        try:
            final_allocated_gb = bytes_to_gb(torch.cuda.memory_allocated())
            final_reserved_gb = bytes_to_gb(torch.cuda.memory_reserved())
            freed_allocated_gb = initial_allocated_gb - final_allocated_gb
            print(f"[Memory Utils] GPU VRAM After: Allocated={final_allocated_gb:.2f}GB, Reserved={final_reserved_gb:.2f}GB")
            print(f"[Memory Utils] GPU VRAM Freed (Allocated): {freed_allocated_gb:.3f} GB")
        except Exception as e:
            print(f"[Memory Utils] Warning: Could not get final VRAM stats - {e}")

    def free_system_ram(self, aggressive):
        """Frees System RAM using garbage collection and optionally system-level cache clearing."""
        print("[Memory Utils] Attempting to Free System RAM...")

        # Initial RAM stats
        initial_memory_info = psutil.virtual_memory()
        initial_percent = initial_memory_info.percent
        initial_available_gb = bytes_to_gb(initial_memory_info.available)
        print(f"[Memory Utils] System RAM Before: Usage={initial_percent:.1f}%, Available={initial_available_gb:.2f}GB")

        # Garbage collection
        collected = gc.collect()
        print(f"[Memory Utils] Garbage Collector: Collected {collected} objects.")

        # Aggressive cleanup (system caches)
        if aggressive:
            print("[Memory Utils] Aggressive Mode: Attempting System Cache clearing...")
            if os.name == 'posix': # Linux/macOS
                if os.geteuid() != 0:
                    print("[Memory Utils] WARNING: Not running as root. Clearing system caches requires root privileges and will likely fail.")

                # 1. Sync filesystem buffers
                try:
                    print("[Memory Utils] Running 'sync' command...")
                    sync_process = subprocess.run(['sync'], check=True, capture_output=True, text=True, timeout=30)
                    print("[Memory Utils] 'sync' completed.")
                except FileNotFoundError: print("[Memory Utils] Error: 'sync' command not found.")
                except subprocess.CalledProcessError as e: print(f"[Memory Utils] Error running sync: Code {e.returncode}\nStderr: {e.stderr.strip()}")
                except subprocess.TimeoutExpired: print("[Memory Utils] Error: 'sync' command timed out after 30s.")
                except Exception as e: print(f"[Memory Utils] Unexpected error during sync: {str(e)}")

                # 2. Drop caches
                try:
                    print("[Memory Utils] Attempting to drop caches via tee (writing '3' to /proc/sys/vm/drop_caches)...")
                    # Using tee allows writing to the file even if the script itself doesn't have direct write permissions,
                    # provided the script is run with sudo which grants tee the permission.
                    drop_process = subprocess.run(
                        ['tee', '/proc/sys/vm/drop_caches'],
                        input='3', text=True, check=True, capture_output=True, timeout=10
                    )
                    print("[Memory Utils] Command 'tee /proc/sys/vm/drop_caches' executed.")
                    # Sometimes tee might succeed but print info to stderr, check just in case
                    if drop_process.stderr: print(f"[Memory Utils] Note: tee command produced stderr: {drop_process.stderr.strip()}")
                except FileNotFoundError: print("[Memory Utils] Error: 'tee' command not found.")
                except subprocess.CalledProcessError as e: print(f"[Memory Utils] Error dropping caches via tee: Code {e.returncode}\nStderr: {e.stderr.strip()}\n(This usually means insufficient permissions - run ComfyUI/script as root/sudo)")
                except subprocess.TimeoutExpired: print("[Memory Utils] Error: 'tee' command timed out after 10s.")
                except Exception as e: print(f"[Memory Utils] Unexpected error during drop caches via tee: {str(e)}")

            elif os.name == 'nt': # Windows
                try:
                    print("[Memory Utils] Attempting to clear working set on Windows via EmptyWorkingSet...")
                    # Get handle to current process
                    current_process_handle = ctypes.windll.kernel32.GetCurrentProcess()
                    if not current_process_handle:
                        raise ctypes.WinError(ctypes.get_last_error())

                    # Call EmptyWorkingSet
                    if ctypes.windll.psapi.EmptyWorkingSet(current_process_handle):
                        print("[Memory Utils] Windows EmptyWorkingSet call succeeded.")
                    else:
                        # Get error details if it failed
                        error_code = ctypes.get_last_error()
                        print(f"[Memory Utils] Windows EmptyWorkingSet call failed. Error code: {error_code}")
                        # Consider raising ctypes.WinError(error_code) if failure is critical
                except AttributeError:
                     print("[Memory Utils] Failed to call EmptyWorkingSet: psapi.EmptyWorkingSet or kernel32.GetCurrentProcess not found (permissions or incompatible Windows version?).")
                except OSError as e: # Catches WinError
                    print(f"[Memory Utils] Failed to clear working set on Windows (OSError): {str(e)}")
                except Exception as e:
                    print(f"[Memory Utils] Unexpected error clearing working set on Windows: {str(e)}")
            else:
                print(f"[Memory Utils] Aggressive system RAM clearing not implemented for OS: {os.name}")
        else:
             print("[Memory Utils] Non-Aggressive Mode: System cache clearing skipped.")


        # Final RAM stats
        final_memory_info = psutil.virtual_memory()
        final_percent = final_memory_info.percent
        final_available_gb = bytes_to_gb(final_memory_info.available)
        memory_freed_percent_points = initial_percent - final_percent
        available_change_gb = final_available_gb - initial_available_gb

        print(f"[Memory Utils] System RAM After: Usage={final_percent:.1f}%, Available={final_available_gb:.2f}GB")
        print(f"[Memory Utils] System RAM Usage Change: {memory_freed_percent_points:+.1f} percentage points") # Show +/-
        print(f"[Memory Utils] System RAM Available Change: {available_change_gb:+.2f} GB") # Show +/-

# === Passthrough Node Implementations ===

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

class FreeMemoryString(FreeMemoryBase):
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
                    # Use forceInput to make it an input connector, not a text widget
                    "string": ("STRING", {"forceInput": True}),
                    "aggressive": ("BOOLEAN", {"default": False})
               }}
    RETURN_TYPES = ("STRING",)
    FUNCTION = "free_memory_passthrough"
    CATEGORY = "Memory Utils"

    def free_memory_passthrough(self, string, aggressive):
        # Input 'string' is just a trigger. We log part of it for debugging.
        print(f"[Memory Utils] FreeMemoryString triggered by string input (starts with: '{str(string)[:50]}...')")
        self.free_memory(aggressive=aggressive)
        return (string,) # Pass the triggering string through

# === Node Mappings for ComfyUI ===

NODE_CLASS_MAPPINGS = {
    "FreeMemoryImage": FreeMemoryImage,
    "FreeMemoryLatent": FreeMemoryLatent,
    "FreeMemoryModel": FreeMemoryModel,
    "FreeMemoryCLIP": FreeMemoryCLIP,
    "FreeMemoryString": FreeMemoryString,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "FreeMemoryImage": "🐍 Free Memory (Image)",
    "FreeMemoryLatent": "🐍 Free Memory (Latent)",
    "FreeMemoryModel": "🐍 Free Memory (Model)",
    "FreeMemoryCLIP": "🐍 Free Memory (CLIP)",
    "FreeMemoryString": "🐍 Free Memory (String Trigger)",
}

print('------------------------------------')
print('Loaded Memory Utils Custom Nodes:')
print('- FreeMemoryImage')
print('- FreeMemoryLatent')
print('- FreeMemoryModel')
print('- FreeMemoryCLIP')
print('- FreeMemoryString')
print('------------------------------------')

# --- End of File ---
