from vispy import app, scene, visuals, gloo, plot
from vispy.scene.visuals import create_visual_node
from vispy.util import filter 
import numpy as np


class ScrollingLinesVisual(visuals.Visual):
    vertex_code = """
    attribute vec2 index;  // .x=line #, .y=vertex #
    uniform sampler2D position;
    
    uniform vec2 pos_size;
    uniform float offset;
    uniform int columns;
    uniform float dt;
    uniform vec2 cell_size;
    
    varying vec2 v_index;
    
    
    void main() {
        v_index = vec2(mod(index.x + offset, pos_size.x), index.y);
        vec4 pos = vec4(index.x * dt, texture2D(position, v_index / (pos_size-1)).r, 0, 1);
        float col = mod(v_index.y, columns);
        float row = (v_index.y - col) / columns;
        pos = pos + vec4(col * cell_size.x, row * cell_size.y, 0, 0);
        gl_Position = $transform(pos);
    }
    """
    
    fragment_code = """
    varying vec2 v_index;
    
    void main() {
        if (v_index.y - floor(v_index.y) > 0) {
            discard;
        }
        gl_FragColor = vec4(1, 1, 1, 1);
    }
    """
    
    def __init__(self, n_lines, line_size, dt, columns=1, cell_size=(1, 1)):
        """Displays many lines of equal length, with the option to add new
        vertex data to one end of the lines.
        """
        self._pos_data = None
        self._offset = 0
        
        data = np.zeros((n_lines, line_size), dtype='float32')
        self._pos_tex = gloo.Texture2D(data, format='luminance', internalformat='r32f')
        self._index_buf = gloo.VertexBuffer()
        self._data_shape = data.shape
        
        visuals.Visual.__init__(self, vcode=self.vertex_code, fcode=self.fragment_code)
        
        self.shared_program['position'] = self._pos_tex
        self.shared_program['index'] = self._index_buf
        self.shared_program['columns'] = columns
        self.shared_program['cell_size'] = cell_size
        self.shared_program['dt'] = dt
        self.shared_program['pos_size'] = data.shape[::-1]
        self.shared_program['offset'] = self._offset
        
        index = np.empty((data.shape[0], data.shape[1], 2), dtype='float32')
        index[..., 1] = np.arange(data.shape[0])[:, np.newaxis]
        index[..., 0] = np.arange(data.shape[1])[np.newaxis, :]
        index = index.reshape((index.shape[0]*index.shape[1], index.shape[2]))
        self._index_buf.set_data(index)
        
        self._draw_mode = 'line_strip'
        self.set_gl_state('translucent', line_width=1)

    def _prepare_transforms(self, view):
        view.view_program.vert['transform'] = view.get_transform().simplified
        
    def _prepare_draw(self, view):
        pass
    
    def _compute_bounds(self, axis, view):
        if self._pos_data is None:
            return None
        return self._pos_data[..., axis].min(), self.pos_data[..., axis].max()
    
    def roll_data(self, data):
        data = data.astype('float32')[..., np.newaxis]
        s1 = self._data_shape[1] - self._offset
        if data.shape[1] > s1:
            self._pos_tex[:, self._offset:] = data[:, :s1]
            self._pos_tex[:, :data.shape[1] - s1] = data[:, s1:]
            self._offset = (self._offset + data.shape[1]) % self._data_shape[1]
        else:
            self._pos_tex[:, self._offset:self._offset+data.shape[1]] = data
            self._offset += data.shape[1]
        self.shared_program['offset'] = self._offset
        self.update()


ScrollingLines = create_visual_node(ScrollingLinesVisual)

win = scene.SceneCanvas(keys='interactive', show=True, size=(1024, 768))
grid = win.central_widget.add_grid()
view = grid.add_view(0, 1)
view.camera = scene.MagnifyCamera(mag=3, size_factor=0.3, radius_ratio=0.6)
#view.camera = 'panzoom'

# Add axes
yax = scene.AxisWidget(orientation='left')
yax.stretch = (0.05, 1)
grid.add_widget(yax, 0, 0)
yax.link_view(view)

xax = scene.AxisWidget(orientation='bottom')
xax.stretch = (1, 0.05)
grid.add_widget(xax, 1, 1)
xax.link_view(view)


N = 10000
M = 2000
cols = int(N**0.5)
view.camera.rect = (0, 0, cols, N/cols)

lines = ScrollingLines(n_lines=N, line_size=M, columns=cols, dt=0.8/M,
                       cell_size=(1, 8), parent=view.scene)
lines.transform = scene.STTransform(scale=(1, 1/8.))

def update(ev):
    m = 10
    data = np.zeros((N, m))
    data = np.random.normal(size=(N, m), scale=0.3)
    data[data > 1] += 4
    lines.roll_data(data)

timer = app.Timer(connect=update, interval=0)
timer.start()


if __name__ == '__main__':
    import sys
    if sys.flags.interactive != 1:
        app.run()
