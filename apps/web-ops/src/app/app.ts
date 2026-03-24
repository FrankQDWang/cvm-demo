import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  readonly title = '运行监控台';
  readonly subtitle = '查看寻访批次、失败分类、延迟、版本与 Temporal visibility 诊断。';
}
